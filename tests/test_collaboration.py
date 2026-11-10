"""Consequential coordination doubles; these are not real Codex science receipts."""
from contextlib import contextmanager, redirect_stdout
import io
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from tests import use_checkout
use_checkout()
from research_pipeline import checkpoint, cli, codex, collaboration, isolation, workspace


ASSIGNMENT = """# Dependent comparison
## Objective
Compute the correction to the parent approximation.
## Parent question
Does the leading approximation adequately describe the reference calculation?
## Scientific benefit
Resolve the error estimate while the primary derives the leading term.
## Assumptions
Use the same finite reference parameters.
## Requested result
Save a reproducible correction with uncertainty and limitations.
## Artifacts
[Plan](PLAN.md)
"""


def handoff(task_id, artifact):
    return f"""Logical researcher: {task_id}
## Objective
Continue the approximation comparison.
## Parent question
Quantify the correction needed by the parent.
## Completed
Computed a reference and saved reusable data.
## Artifacts
[Data](/project/{artifact})
## Assumptions
Finite reference parameters; preliminary interpretation.
## Unresolved
Approximation applicability remains uncertain.
## Next action
Compare the saved reference with the leading approximation.
## Interrupted computation
None; reference has been saved.
## Resume or reconsider
Resume the error analysis from saved reference data.
"""


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'project'
        (self.project / 'starting_evidence').mkdir(parents=True)
        (self.project / 'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Assess an approximation and its correction.')
        (self.project / 'AGENTS.md').write_text('Use explicit uncertainty.')
        self.services = []
        self.parent_progress = []
        self.mode = 'normal'
        self.ack_delay = 0
        self.units_stopped = []
        self.saving_notices = []

    def state(self):
        return json.loads((self.project / '.research_pipeline/run.json').read_text())

    def draft(self, config, rel, text):
        p = config.drafts / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    @contextmanager
    def backend(self):
        case = self
        self.clock = 1000.0
        def sleep(seconds):
            self.clock += .25
        @contextmanager
        def auth(project):
            with tempfile.TemporaryDirectory(dir=project / '.research_pipeline') as name:
                yield Path(name)
        def preflight(config, project):
            config.on_probe_launch(f'research-{uuid.uuid4().hex}.service')
            return {'observed_cgroup_limits': {'memory_max': str(config.memory_mib * 1024**2),
                                              'memory_swap_max': '0', 'pids_max': str(config.max_tasks)}}
        def stop(unit):
            self.units_stopped.append(unit)
            return not (case.mode == 'unclean' and len(self.services) > 1)

        class Service:
            def __init__(self, config, project, command, prompt, recorder, auth):
                self.config, self.recorder = config, recorder
                self.command, self.prompt = command, prompt
                self.task_id = config.task_id
                self.number = sum(s.task_id == self.task_id for s in case.services)
                self.result = isolation.ExecutionResult(0, cleanup_ok=True)
                self.ticks = 0
                self.finished = False
                self.acknowledged_at = None
                self.request_seen_at = None
                case.services.append(self)
                recorder('stdout', (json.dumps({'type':'thread.started', 'thread_id':f'native-{len(case.services)}'}) + '\n').encode())
                recorder('stdout', b'{"type":"item.completed","item":{"type":"command_execution","exit_code":0}}\n')
                recorder('stdout', b'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}\n')
                if self.task_id == 'primary':
                    case.draft(config, 'work/PLAN.md', '# Plan\nDerive the leading term while the dependent task calculates its correction. [Reference](reference.csv)')
                    case.draft(config, 'sources/LITERATURE.md', '# Literature\nNo external source needed for this engineering fixture.')
                    case.draft(config, 'work/ASSIGNMENT.md', ASSIGNMENT)
                    (project / 'work/reference.csv').write_text('x,value\n1,2\n')
                    case.draft(config, 'handoffs/primary.md', handoff('primary', 'work/reference.csv'))
                    case.draft(config, 'RESEARCH_STATUS.md', '# Status\nAssessing approximation error.')
                    view = config.on_poll.__self__.view
                    request = {**workspace.owner_fields(view), 'task_id': 'primary',
                               'nonce': uuid.uuid4().hex, 'parent_task': 'primary', 'assignment': 'work/ASSIGNMENT.md'}
                    if not self.number:
                        (config.response / 'delegation.json').write_text(json.dumps(request))
                else:
                    root = workspace.task_directory(self.task_id)
                    if self.number:
                        assert 'Computed a reference and saved reusable data.' in prompt
                        assert (project / root / 'reference.csv').read_text() == 'x,value\n1,2\n'
                        (project / root / 'comparison.csv').write_text('x,error\n1,0.1\n')
                    else:
                        assert (project / root / 'ASSIGNMENT.md').is_file()
                        assert '/project/work/reference.csv' in (project / root / 'assignment-input-0.md').read_text()
                        (project / root / 'reference.csv').write_text('x,value\n1,2\n')
                    case.draft(config, f'handoffs/{self.task_id}.md', handoff(self.task_id, root + '/reference.csv'))
                    case.draft(config, root + '/RESULT.md', '# Preliminary correction\nThe correction is 0.1 in this fixture. Finite parameter uncertainty remains. [Reference](reference.csv)')
                    if case.mode == 'invalid-draft':
                        case.draft(config, 'outputs/REPORT.md', '# Forbidden child replacement')
                    # Production duration is 16 seconds: first rollover request occurs one second after launch.

            def poll(self):
                self.ticks += 1
                if case.clock >= self.config.deadline:
                    self.result.timed_out = True
                    return True
                reason = self.config.on_poll()
                request = workspace.read_control(self.config.control / 'request.json')
                if request:
                    if self.request_seen_at is None:
                        self.request_seen_at = case.clock
                    if case.mode == 'pause-during-saving' and request['reason'] == 'rollover':
                        self.config.on_poll.__self__.coordinator.request_stop('pause')
                        return False
                    if case.clock - self.request_seen_at < case.ack_delay:
                        return bool(reason)
                    if case.mode != 'no-ack':
                        (self.config.response / 'ready.json').write_text(json.dumps({**request, 'readiness_nonce': uuid.uuid4().hex}))
                        self.config.on_poll()
                        ack = workspace.read_control(self.config.control / 'ack.json')
                        if ack and ack.get('accepted'):
                            self.acknowledged_at = case.clock
                            if case.mode == 'human-handoff' and self.task_id != 'primary':
                                (case.project / workspace.handoff_path(self.task_id)).write_text('# Human correction preserved')
                            return True
                    return bool(reason)
                if self.task_id == 'primary':
                    if case.mode == 'saving-notice':
                        output = io.StringIO()
                        with patch.object(checkpoint, 'Path', return_value=self.config.control), \
                             patch.object(sys, 'argv', ['checkpoint', '--check']), redirect_stdout(output):
                            case.assertEqual(checkpoint.main(), 0)
                        for line in output.getvalue().splitlines():
                            if not line.startswith('Concurrent task status: '):
                                continue
                            for summary in json.loads(line.removeprefix('Concurrent task status: ')):
                                case.saving_notices.append(summary)
                                if summary['saving_reason'] == 'rollover':
                                    # The signal must arrive before the child publishes,
                                    # so the parent can extend its own study immediately.
                                    case.assertFalse((case.project / workspace.handoff_path(summary['task_id'])).exists())
                                    (case.project / 'work/parent-extension.csv').write_text('x,value\n2,4\n')
                    case.parent_progress.append((case.clock, len(case.services)))
                    if case.mode == 'pause' and len(case.services) > 1:
                        state = case.state()
                        _, control, _ = workspace.control_paths(case.project, state)
                        workspace.atomic_text(control / 'request.json', json.dumps({'version':1,
                            **workspace.owner_fields(state), 'request_id':uuid.uuid4().hex, 'reason':'pause'}))
                    if case.mode == 'early-primary' and len(case.services) > 1:
                        return True
                    tasks = case.state()['tasks']
                    child = next((t for t in tasks.values() if t['role'] != 'primary'), None)
                    if child and child['status'] in ('completed', 'failed', 'interrupted', 'incomplete', 'timed_out'):
                        if child['status'] == 'completed':
                            link = child['delivery']['result']
                            case.draft(self.config, 'outputs/REPORT.md',
                                f'# Preliminary synthesis\nThe [dependent correction](../{link}) changes the parent estimate by 0.1. '
                                'Finite parameter uncertainty limits applicability. [Reference](../work/reference.csv)')
                        return True
                elif self.number:
                    return True
                return False

            def finish(self):
                self.finished = True
                if case.mode == 'unclean' and self.task_id != 'primary':
                    self.result.cleanup_ok = False
                return self.result

        with patch.object(codex, 'private_auth', auth), \
             patch.object(codex, 'verify_backend', return_value={'version':'engineering double'}), \
             patch.object(isolation, 'preflight', side_effect=preflight), \
             patch.object(isolation, 'RunningService', Service), \
             patch.object(isolation, 'stop_service', side_effect=stop), \
             patch.object(collaboration.time, 'monotonic', side_effect=lambda: self.clock), \
             patch.object(collaboration.time, 'sleep', side_effect=sleep):
            yield

    def start(self, mode='normal', primary_seconds='300', delegated_seconds='16', wall_seconds='100'):
        self.mode = mode
        with self.backend(), redirect_stdout(io.StringIO()):
            return cli.main(['start', str(self.project), '--wall-seconds', wall_seconds, '--max-agents', '2',
                             '--memory-mib', '512', '--max-tasks', '64', '--delegated-session-seconds', delegated_seconds,
                             '--primary-session-seconds', primary_seconds])

    def test_dependent_delivery_integrated_after_fresh_rollover_while_parent_progresses(self):
        self.assertEqual(self.start(), 0, self.state())
        state = self.state()
        child = next(t for t in state['tasks'].values() if t['role'] == 'researcher')
        self.assertEqual(state['state'], 'completed')
        self.assertEqual(child['status'], 'completed')
        self.assertEqual(child['parent_task'], 'primary')
        self.assertEqual(child['integration'], ['outputs/REPORT.md'])
        self.assertEqual(len(self.services), 3)
        self.assertTrue(all(s.finished for s in self.services))
        self.assertEqual(state['usage_totals'], {'input_tokens': 30, 'output_tokens': 6})
        self.assertEqual([s['task_id'] for s in state['sessions']].count(child['task_id']), 2)
        self.assertTrue(all(s.config.memory_mib == 256 and s.config.max_tasks == 32 for s in self.services))
        self.assertLess(state['active_seconds'], sum(s['active_seconds'] for s in state['sessions']))
        self.assertEqual(state['remaining_active_seconds'], 100 - state['active_seconds'])
        self.assertIn((self.project / child['workspace'] / 'comparison.csv').read_text(), 'x,error\n1,0.1\n')
        self.assertTrue(any(n == 2 for _, n in self.parent_progress))
        self.assertTrue(any(n == 3 for _, n in self.parent_progress))
        self.assertIn('--ephemeral', self.services[-1].command)
        self.assertNotIn('resume', self.services[-1].command)
        self.assertIn('PRELIMINARY', self.services[-1].prompt)
        self.assertEqual(len({s['native_session_id'] for s in state['sessions']}), 3)
        self.assertTrue(state['cleanup_ok'])
        for path in (self.project / child['workspace'], self.project / 'handoffs', self.project / 'work/tasks'):
            self.assertTrue((path / 'FOLDER_CONTENT.md').is_file())

    def test_primary_rollover_preserves_sibling_task_and_fresh_ownership(self):
        self.assertEqual(self.start(primary_seconds='16'), 0, self.state())
        state = self.state()
        self.assertEqual(len([s for s in self.services if s.task_id == 'primary']), 2)
        children = [s for s in self.services if s.task_id != 'primary']
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0].task_id, children[1].task_id)
        self.assertEqual(len(state['tasks']), 2)
        self.assertEqual(len({s['native_session_id'] for s in state['sessions']}), 4)
        self.assertTrue(state['cleanup_ok'])

    def test_primary_observes_child_saving_before_publication_and_fresh_successor(self):
        self.ack_delay = 2
        self.assertEqual(self.start('saving-notice'), 0, self.state())
        child = next(t for t in self.state()['tasks'].values() if t['role'] == 'researcher')
        saving = [n for n in self.saving_notices if n['saving_reason'] == 'rollover']
        self.assertTrue(saving, 'Primary never learned that its child was saving')
        self.assertEqual((self.project / 'work/parent-extension.csv').read_text(), 'x,value\n2,4\n')
        self.assertTrue(any(n['activation_id'] == child['activation']['activation_id']
                            and n['activation_id'] != saving[0]['activation_id']
                            and n['saving_reason'] is None for n in self.saving_notices),
                        'Successor retained a stale saving notice or identity')
        self.assertEqual(len(self.services), 3)
        self.assertTrue(self.state()['cleanup_ok'])

    def test_own_saving_request_takes_precedence_over_concurrent_status(self):
        control = self.project / 'helper-control'
        control.mkdir()
        (control / 'request.json').write_text(json.dumps({'reason': 'pause'}))
        # A primary pause must be actionable even without a readable tasks snapshot.
        (control / 'tasks.json').write_text('incomplete snapshot')
        output = io.StringIO()
        with patch.object(checkpoint, 'Path', return_value=control), \
             patch.object(sys, 'argv', ['checkpoint', '--check']), redirect_stdout(output):
            self.assertEqual(checkpoint.main(), 0)
        self.assertIn('PAUSE REQUESTED', output.getvalue())
        self.assertNotIn('Concurrent task status', output.getvalue())

    def test_slow_model_handoff_rolls_primary_and_child_without_extending_limits(self):
        self.ack_delay = 20  # The real runs missed the old 15-second reserve.
        self.assertEqual(self.start(primary_seconds='240', delegated_seconds='240',
                                    wall_seconds='500'), 0, self.state())
        state = self.state()
        self.assertEqual(len(self.services), 4)
        for service in self.services[:2]:
            self.assertGreaterEqual(service.acknowledged_at - service.request_seen_at, 20)
            self.assertLess(service.acknowledged_at, service.config.deadline)
            self.assertEqual(service.config.deadline - service.request_seen_at, 60)
            self.assertIn('rollover reserves 60 seconds', service.prompt)
        self.assertEqual(len({s['native_session_id'] for s in state['sessions']}), 4)
        self.assertEqual(state['usage_totals'], {'input_tokens': 40, 'output_tokens': 8})
        self.assertEqual(state['remaining_active_seconds'], 500 - state['active_seconds'])
        self.assertTrue(all(s.finished and not s.result.timed_out for s in self.services))

    def test_pause_shortens_rollover_saving_without_waiting_for_slow_model(self):
        self.ack_delay = 100
        self.assertEqual(self.start('pause-during-saving', primary_seconds='240',
                                    delegated_seconds='240', wall_seconds='500'), 0)
        self.assertEqual(self.state()['state'], 'paused')
        self.assertEqual(len(self.services), 2)
        for service in self.services:
            self.assertLessEqual(self.clock - service.request_seen_at, 15.5)
            self.assertTrue(service.finished)
        self.assertTrue(self.state()['cleanup_ok'])

    def test_slow_launch_preparation_services_sibling_rollover_before_deadline(self):
        stages = []
        def slow_stage(config, poll):
            if config.task_id != 'primary' and len(self.services) == 1:
                stages.append(self.clock)
                for _ in range(40):
                    self.clock += .25
                    poll()

        def verify(config, on_wait=None):
            slow_stage(config, on_wait or (lambda: None))
            return {'version': 'slow inspection engineering double'}

        with self.backend(), redirect_stdout(io.StringIO()):
            original_preflight = isolation.preflight.side_effect
            def preflight(config, project):
                result = original_preflight(config, project)
                slow_stage(config, lambda: config.on_poll(research=False))
                return result
            with patch.object(codex, 'verify_backend', side_effect=verify), \
                 patch.object(isolation, 'preflight', side_effect=preflight):
                code = cli.main(['start', str(self.project), '--max-agents', '2',
                                 '--wall-seconds', '100', '--primary-session-seconds', '16',
                                 '--delegated-session-seconds', '16'])
        self.assertEqual(code, 0, self.state())
        self.assertEqual(len(stages), 2, 'Both backend inspection and preflight must overlap the primary')
        predecessor = self.services[0]
        self.assertTrue(predecessor.finished)
        self.assertIsNotNone(predecessor.acknowledged_at)
        self.assertLess(predecessor.acknowledged_at, predecessor.config.deadline)
        self.assertGreater(stages[-1] + 10, predecessor.config.deadline,
                           'Preparation must last beyond the old context deadline')
        primaries = [s for s in self.services if s.task_id == 'primary']
        self.assertGreaterEqual(len(primaries), 2)
        self.assertIn('Computed a reference and saved reusable data.', primaries[1].prompt)
        self.assertTrue(self.state()['cleanup_ok'])
        self.assertTrue(all(not s.result.timed_out for s in self.services))
        self.assertTrue(all(t['status'] == 'completed' for t in self.state()['tasks'].values()))

    def test_backend_inspection_polls_during_subprocess_wait_and_cleans_up_on_pause(self):
        popen = subprocess.Popen
        processes, polls = [], []
        def inspect_process(argv, **kwargs):
            output = ('--ignore-user-config --ignore-rules --ephemeral --json --sandbox'
                      if argv[-1] == '--help' else 'inspection test backend')
            process = popen([sys.executable, '-c',
                             f'import time; time.sleep(.25); print({output!r})'], **kwargs)
            processes.append(process)
            return process
        config = isolation.Config(codex=sys.executable, deadline=time.monotonic() + 5)
        with patch.object(codex.subprocess, 'Popen', side_effect=inspect_process):
            backend = codex.verify_backend(config, on_wait=lambda: polls.append(time.monotonic()))
            self.assertEqual(backend['version'], 'inspection test backend')
            self.assertGreater(len(polls), 4, 'Both inspection commands must keep polling while waiting')
            self.assertTrue(all(p.poll() == 0 for p in processes))
            with self.assertRaisesRegex(isolation.RequestedStop, 'pause'):
                codex.verify_backend(config, on_wait=lambda: 'pause')
        self.assertIsNotNone(processes[-1].poll(), 'Cancelled inspection subprocess must be reaped')

    def test_sibling_continues_after_rollover_even_if_preparing_launch_fails(self):
        def verify(config, on_wait=None):
            if config.task_id != 'primary':
                for _ in range(8):
                    self.clock += .25
                    on_wait()
                raise isolation.RuntimeUnavailable('Delegated backend unavailable')
            return {'version': 'engineering double'}
        with self.backend(), redirect_stdout(io.StringIO()), \
             patch.object(codex, 'verify_backend', side_effect=verify):
            code = cli.main(['start', str(self.project), '--max-agents', '2',
                             '--wall-seconds', '100', '--primary-session-seconds', '16'])
        self.assertEqual(code, 4, 'The failed dependent task must remain incomplete')
        self.assertEqual(len(self.services), 2)
        self.assertTrue(all(s.task_id == 'primary' for s in self.services))
        self.assertIsNotNone(self.services[0].acknowledged_at)
        self.assertIn('Computed a reference and saved reusable data.', self.services[1].prompt)
        state = self.state()
        self.assertEqual(state['tasks']['primary']['status'], 'completed')
        child = next(t for t in state['tasks'].values() if t['role'] != 'primary')
        self.assertIn('Delegated backend unavailable', child['checkpoint_error'])
        self.assertTrue(state['cleanup_ok'])

    def test_human_handoff_edit_wins_and_blocks_only_child_rollover(self):
        self.assertEqual(self.start('human-handoff'), 4)
        state = self.state()
        child = next(t for t in state['tasks'].values() if t['role'] != 'primary')
        self.assertEqual((self.project / workspace.handoff_path(child['task_id'])).read_text(), '# Human correction preserved')
        self.assertEqual(child['status'], 'interrupted')
        self.assertIn('conflicts with a human edit', child['checkpoint_error'])
        self.assertEqual(len(self.services), 2)
        self.assertGreater(len(self.parent_progress), 2)
        self.assertTrue(state['cleanup_ok'])

    def test_full_pause_stops_both_tasks_and_prevents_successor(self):
        self.assertEqual(self.start('pause'), 0, self.state())
        state = self.state()
        self.assertEqual(state['state'], 'paused')
        self.assertEqual(len(self.services), 2)
        self.assertTrue(all(s.finished for s in self.services))
        self.assertTrue(all(a['cleanup_ok'] for a in collaboration.owned_activations(state)))
        self.assertTrue(all(t['checkpoint'] for t in state['tasks'].values()))

    def test_resume_keeps_grants_and_task_identity_but_reloads_human_inputs(self):
        self.assertEqual(self.start('pause'), 0)
        previous = self.state()
        (self.project / 'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Revised question: assess endpoint sensitivity.')
        (self.project / 'AGENTS.md').unlink()
        (self.project / 'HUMAN_FEEDBACK.md').write_text('Retain the reference and reconsider applicability.')
        (self.project / 'work/PLAN.md').write_text('# Human plan correction\nCompare endpoint sensitivity.')
        self.mode = 'normal'
        with self.backend(), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['resume', str(self.project)]), 0, self.state())
        state = self.state()
        self.assertEqual(state['limits'], previous['limits'])
        self.assertEqual(state['delegated_session_policy'], previous['delegated_session_policy'])
        self.assertEqual(set(state['tasks']), set(previous['tasks']))
        self.assertEqual(state['run_id'], previous['run_id'])
        self.assertNotEqual(state['ownership_nonce'], previous['ownership_nonce'])
        self.assertGreater(state['active_seconds'], previous['active_seconds'])
        self.assertEqual(state['usage_totals'], {'input_tokens':40, 'output_tokens':8})
        for service in self.services[2:]:
            self.assertIn('Revised question: assess endpoint sensitivity.', service.prompt)
            self.assertIn('Retain the reference and reconsider applicability.', service.prompt)
            self.assertIn('Use explicit uncertainty.', service.prompt)
            self.assertIn('Human plan correction', ''.join(p.read_text() for p in (self.project / 'handoffs/preserved').glob('*.md')))
        self.assertTrue(state['cleanup_ok'])

    def test_resume_reserves_primary_rollover_slot_while_child_preflight_is_slow(self):
        self.assertEqual(self.start('pause', primary_seconds='16'), 0)
        previous = self.state()
        child = next(t for t in previous['tasks'].values() if t['role'] != 'primary')
        coordinator = collaboration.Coordinator(self.project, previous, isolation.Config())
        primary_session = self.project / '.research_pipeline/sessions' / previous['tasks']['primary']['activation']['activation_id']
        extra = coordinator.read_assignment('work/ASSIGNMENT.md', 'primary', primary_session / 'drafts')
        extra['status'] = 'interrupted'
        previous['tasks'][extra['task_id']] = extra
        coordinator.recovery_handoff(extra, 'Unfinished dependent task awaiting a free slot.')
        coordinator.save()

        self.mode = 'normal'
        snapshots = []
        resumed_services = len(self.services)
        with self.backend(), redirect_stdout(io.StringIO()):
            original_preflight = isolation.preflight.side_effect
            def preflight(config, project):
                result = original_preflight(config, project)
                if config.task_id == child['task_id']:
                    for _ in range(8):
                        self.clock += .25
                        config.on_poll(research=False)
                    snapshots.append(self.state())
                return result
            with patch.object(isolation, 'preflight', side_effect=preflight):
                code = cli.main(['resume', str(self.project)])

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]['tasks']['primary']['status'], 'rolling_over',
                         'Primary must hand off during the first child preflight')
        self.assertEqual(code, 4, 'The unstarted extra task must leave the investigation incomplete')
        state = self.state()
        self.assertEqual(state['tasks']['primary']['status'], 'completed', state['reason'])
        self.assertEqual(state['tasks'][child['task_id']]['status'], 'completed')
        self.assertEqual(state['tasks'][extra['task_id']]['status'], 'interrupted')
        self.assertIsNone(state['tasks'][extra['task_id']]['activation'],
                          'Additional tasks must not take the pending primary successor slot')
        self.assertIn('No free slot on resume', state['tasks'][extra['task_id']]['interrupted_work'])
        self.assertNotIn('Stopped:', state['reason'])
        successors = [s for s in self.services[resumed_services:] if s.task_id == 'primary']
        self.assertEqual(len(successors), 2)
        self.assertIsNotNone(successors[0].acknowledged_at)
        self.assertIn('Computed a reference and saved reusable data.', successors[1].prompt)
        self.assertEqual(state['limits'], previous['limits'])
        self.assertGreater(state['active_seconds'], previous['active_seconds'])
        self.assertTrue(state['cleanup_ok'])
        self.assertTrue(all(s.finished for s in self.services))

    def test_primary_exit_stops_unfinished_children_and_reports_incomplete(self):
        self.assertEqual(self.start('early-primary'), 4)
        self.assertEqual(self.state()['state'], 'incomplete')
        self.assertIn('unfinished', self.state()['reason'])
        self.assertTrue(all(s.finished for s in self.services))

    def test_unacknowledged_child_rollover_keeps_partial_science_without_successor(self):
        self.assertEqual(self.start('no-ack'), 4)
        child = next(t for t in self.state()['tasks'].values() if t['role'] != 'primary')
        self.assertEqual(child['status'], 'interrupted')
        self.assertIn('not acknowledged', child['activation']['rollover']['limitation'])
        self.assertTrue((self.project / child['workspace'] / 'reference.csv').exists())
        self.assertEqual(len(self.services), 2)

    def test_invalid_child_publication_preserves_original_and_blocks_successor(self):
        self.assertEqual(self.start('invalid-draft'), 4)
        self.assertEqual(len(self.services), 2)
        self.assertFalse((self.project / 'outputs/REPORT.md').exists())
        child = next(t for t in self.state()['tasks'].values() if t['role'] != 'primary')
        self.assertIn('Invalid scientific draft destination', child['checkpoint_error'])
        self.assertTrue(self.state()['cleanup_ok'])

    def test_uncertain_cleanup_blocks_all_launches_and_retains_pending_accounting(self):
        self.assertEqual(self.start('unclean'), 4)
        self.assertFalse(self.state()['cleanup_ok'])
        self.assertTrue(self.state()['owner_interval']['pending'])
        self.assertEqual(len(self.services), 2)
        with patch.object(isolation, 'stop_service', return_value=False), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['resume', str(self.project)]), 2)

    def test_assignment_capacity_ownership_and_idempotence(self):
        self.assertEqual(self.start(), 0)
        state = self.state()
        coordinator = collaboration.Coordinator(self.project, state, isolation.Config())
        coordinator.begin_interval()
        primary = state['tasks']['primary']
        view = collaboration.TaskState(coordinator, primary)
        _, control, response = workspace.control_paths(self.project, view)
        runtime = {'task': primary, 'view': view, 'config': isolation.Config(control=control, response=response,
                   drafts=control.parent / 'drafts')}
        request = {**workspace.owner_fields(view), 'task_id':'primary', 'nonce':uuid.uuid4().hex,
                   'parent_task':'primary', 'assignment':'work/ASSIGNMENT.md'}
        coordinator.running = {'primary': runtime, 'occupied': runtime}
        with patch.object(coordinator, 'launch') as launch:
            workspace.atomic_text(response / 'delegation.json', json.dumps(request))
            coordinator.accept_assignment(runtime)
            ack = workspace.read_control(control / 'delegation-ack.json')
            self.assertFalse(ack['accepted'])
            self.assertIn('slots allocated', ack['error'])
            coordinator.running.pop('occupied')
            coordinator.accept_assignment(runtime)
            self.assertEqual(workspace.read_control(control / 'delegation-ack.json'), ack)
            launch.assert_not_called()
            for change, error in (({'ownership_nonce':uuid.uuid4().hex}, 'ownership'),
                                  ({'parent_task':'unknown'}, 'Unknown scientific parent')):
                workspace.atomic_text(response / 'delegation.json', json.dumps({**request, **change, 'nonce':uuid.uuid4().hex}))
                coordinator.accept_assignment(runtime)
                self.assertIn(error, workspace.read_control(control / 'delegation-ack.json')['error'])
            launch.assert_not_called()

    def test_primary_can_continue_existing_task_without_changing_its_identity(self):
        self.assertEqual(self.start(), 0)
        state = self.state()
        coordinator = collaboration.Coordinator(self.project, state, isolation.Config())
        coordinator.begin_interval()
        primary = state['tasks']['primary']
        child = next(t for t in state['tasks'].values() if t['role'] != 'primary')
        child['status'] = 'interrupted'
        identity = {k:child[k] for k in collaboration.IDENTITY_FIELDS if k not in ('activation','status','delivery','integration')}
        view = collaboration.TaskState(coordinator, primary)
        _, control, response = workspace.control_paths(self.project, view)
        runtime = {'task':primary, 'view':view, 'config':isolation.Config(control=control,
                   response=response, drafts=control.parent / 'drafts')}
        coordinator.running = {'primary':runtime}
        request = {**workspace.owner_fields(view), 'task_id':'primary', 'nonce':uuid.uuid4().hex,
                   'assignment':child['assignment'], 'parent_task':'primary'}
        with patch.object(coordinator, 'launch') as launch:
            workspace.atomic_text(response / 'delegation.json', json.dumps(request))
            coordinator.accept_assignment(runtime)
            launch.assert_called_once_with(child)
            self.assertTrue(workspace.read_control(control / 'delegation-ack.json')['accepted'])
            self.assertEqual(len(state['tasks']), 2)
            self.assertEqual(identity, {k:child[k] for k in identity})
            workspace.atomic_text(response / 'delegation.json', json.dumps({**request,
                'nonce':uuid.uuid4().hex, 'parent_task':child['task_id']}))
            coordinator.accept_assignment(runtime)
            self.assertIn('Cannot change', workspace.read_control(control / 'delegation-ack.json')['error'])
            self.assertEqual(launch.call_count, 1)

    def test_recovery_stops_all_services_before_bad_drafts_and_charges_owner_once(self):
        self.assertEqual(self.start(), 0)
        state = self.state()
        state.update(state='running', cleanup_ok=False)
        state['owner_interval'] = {'pending':True, 'initial_active_seconds':7, 'started_epoch':time.time()-20, 'allowance':93}
        child = next(t for t in state['tasks'].values() if t['role'] != 'primary')
        primary = state['tasks']['primary']
        child['checkpoint_prepared'] = f".research_pipeline/sessions/{child['activation']['activation_id']}/bad-preparation"
        child['status'] = 'running'
        stopped = []
        with patch.object(isolation, 'stop_service', side_effect=lambda unit: stopped.append(unit) or True):
            collaboration.recover(self.project, state)
        expected = {a[k] for a in collaboration.owned_activations(state)
                    for k in ('probe_service','service') if a.get(k)}
        self.assertEqual(set(stopped), expected)
        self.assertGreaterEqual(state['active_seconds'], 27)
        self.assertLess(state['active_seconds'], 28)
        self.assertTrue(state['cleanup_ok'])
        self.assertIn('older handoff retained', child['checkpoint_error'])
        before = state['active_seconds']
        with patch.object(isolation, 'stop_service') as stop:
            collaboration.recover(self.project, state)
            stop.assert_not_called()
        self.assertLess(state['active_seconds'] - before, .1)

    def test_killed_foreground_owner_recovers_every_recorded_task(self):
        script = r"""
import os, signal, sys
from pathlib import Path
from unittest.mock import patch
from tests.test_collaboration import CollaborationTests
from research_pipeline import cli, collaboration
case = CollaborationTests()
case.setUp()
case.project = Path(sys.argv[1])
def crash(seconds):
    assert len(case.state()['tasks']) == 2
    assert all(t['activation']['service_attempted'] for t in case.state()['tasks'].values())
    os.kill(os.getpid(), signal.SIGKILL)
with case.backend(), patch.object(collaboration.time, 'sleep', side_effect=crash):
    cli.main(['start', str(case.project), '--max-agents', '2', '--wall-seconds', '100'])
"""
        process = subprocess.run([sys.executable, '-c', script, str(self.project)],
                                 capture_output=True, timeout=5)
        self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
        state = cli.load_state(self.project)
        self.assertTrue(state['owner_interval']['pending'])
        self.assertEqual(len(state['tasks']), 2)
        stopped = []
        with patch.object(isolation, 'stop_service', side_effect=lambda u: stopped.append(u) or True):
            cli.recover_owner(self.project, state)
        self.assertTrue(state['cleanup_ok'])
        self.assertEqual(state['state'], 'interrupted')
        self.assertEqual(len(stopped), 4)
        self.assertTrue(all(t['status'] == 'interrupted' for t in state['tasks'].values()))
        self.assertFalse(state['owner_interval']['pending'])
        self.assertFalse(state['usage_complete'])
        child = next(t for t in state['tasks'].values() if t['role'] != 'primary')
        self.assertTrue((self.project / child['workspace'] / 'reference.csv').exists())
        self.assertIn('Inspect saved science', child['interrupted_work'])

    def test_first_acknowledged_child_checkpoint_survives_controller_crash(self):
        script = r"""
import json, os, signal, sys
from pathlib import Path
from unittest.mock import patch
from tests.test_collaboration import CollaborationTests
from research_pipeline import cli, workspace
case = CollaborationTests()
case.setUp()
case.project = Path(sys.argv[1])
atomic_text = workspace.atomic_text
def crash_after_ack(path, text):
    atomic_text(path, text)
    if path.name == 'ack.json' and json.loads(text).get('accepted'):
        child = next(t for t in case.state()['tasks'].values() if t['role'] != 'primary')
        assert child['checkpoint_prepared']
        assert not child.get('checkpoint')
        assert not (case.project / workspace.handoff_path(child['task_id'])).exists()
        os.kill(os.getpid(), signal.SIGKILL)
with case.backend(), patch.object(workspace, 'atomic_text', side_effect=crash_after_ack):
    cli.main(['start', str(case.project), '--max-agents', '2', '--wall-seconds', '100',
              '--delegated-session-seconds', '16'])
"""
        process = subprocess.run([sys.executable, '-c', script, str(self.project)],
                                 capture_output=True, timeout=5)
        self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
        state = cli.load_state(self.project)
        child = next(t for t in state['tasks'].values() if t['role'] != 'primary')
        canonical = self.project / workspace.handoff_path(child['task_id'])
        session = self.project / '.research_pipeline/sessions' / child['activation']['activation_id']
        expected = (session / 'prepared-handoff.md').read_text()
        self.assertFalse(canonical.exists())
        self.assertTrue(workspace.read_control(session / 'control/ack.json')['accepted'])
        stopped = []
        with patch.object(isolation, 'stop_service', side_effect=lambda unit: stopped.append(unit) or True):
            cli.recover_owner(self.project, state)
        self.assertEqual(len(stopped), 4)
        self.assertTrue(state['cleanup_ok'])
        self.assertEqual(canonical.read_text(), expected)
        self.assertNotIn('checkpoint_prepared', child)
        self.assertNotIn('checkpoint_error', child)
        self.assertEqual(child['pending_reconciliation'], [])
        checkpoint, text, _ = workspace.load_checkpoint(self.project, child)
        self.assertEqual(checkpoint['id'], child['activation']['activation_id'])
        self.assertEqual(text, expected)
        self.assertIn(child['workspace'] + '/reference.csv', checkpoint['artifacts'])
        with patch.object(isolation, 'stop_service') as stop:
            cli.recover_owner(self.project, state)
            stop.assert_not_called()
        self.assertEqual(child['checkpoint'], checkpoint)

    def test_role_scoped_drafts_reject_entire_batch_before_publication(self):
        self.assertEqual(self.start(), 0)
        child = next(t for t in self.state()['tasks'].values() if t['role'] != 'primary')
        drafts = self.project / '.research_pipeline/hostile-drafts'
        drafts.mkdir()
        own = child['workspace'] + '/NEW.md'
        for bad in ('outputs/REPORT.md', 'RESEARCH_STATUS.md', 'handoffs/primary.md',
                    'work/tasks/task-' + 'f'*32 + '/RESULT.md'):
            config = isolation.Config(drafts=drafts)
            self.draft(config, own, '# Acceptable own note')
            self.draft(config, bad, '# Hostile note')
            with self.assertRaisesRegex(workspace.InputError, 'Invalid scientific draft destination'):
                workspace.publish_drafts(self.project, drafts, {}, [], child['task_id'])
            self.assertFalse((self.project / own).exists())
            (drafts / bad).unlink()
        self.draft(config, child['workspace'] + '/RESULT.md', '# Hostile primary draft')
        with self.assertRaisesRegex(workspace.InputError, 'Invalid scientific draft destination'):
            workspace.publish_drafts(self.project, drafts, {}, [], 'primary')

    def test_mount_and_codex_permissions_match_task_workspace(self):
        self.assertEqual(self.start(), 0)
        child = next(t for t in self.state()['tasks'].values() if t['role'] != 'primary')
        command = isolation.bubblewrap_command(self.project, ['/usr/bin/true'], task_id=child['task_id'])
        mounts = [command[i+1:i+3] for i, arg in enumerate(command) if arg == '--bind']
        self.assertIn([str(self.project / child['workspace']), '/project/' + child['workspace']], mounts)
        self.assertNotIn([str(self.project / 'outputs'), '/project/outputs'], mounts)
        self.assertNotIn([str(self.project / 'work'), '/project/work'], mounts)
        config = isolation.Config(task_id=child['task_id'])
        codex_command = codex.build_command(config)
        self.assertIn('/project/' + child['workspace'], codex_command)
        self.assertNotIn('/project/outputs', codex_command)
        primary = isolation.bubblewrap_command(self.project, ['/usr/bin/true'], task_workspaces=('work/tasks',))
        self.assertIn(str(self.project / 'work/tasks'), primary)
        self.assertNotIn(str(self.project / child['workspace'] / 'RESULT.md'), primary,
                         'Do not pin reader inodes: published replacements must remain visible')


if __name__ == '__main__':
    unittest.main()
