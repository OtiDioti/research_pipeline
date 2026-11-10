"""Finite scientific exchange and continuity doubles, not real Codex evidence."""
from contextlib import contextmanager, redirect_stdout
import io
import json
import signal
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

from tests import use_checkout
use_checkout()
from tests import test_collaboration as fixtures
from research_pipeline import cli, codex, collaboration, isolation, verification, workspace

PACKET = """# Scoped comparison
## Claim and scope
The leading estimate has error below 0.05 at x=1.
## Parent question
Can the approximation support the parent conclusion?
## Scientific benefit
Challenge the consequential approximation independently.
## Assumptions and approximation regime
Finite reference parameters; an endpoint correction was neglected.
## Sources and artifacts
[Reference](reference.csv) and [method](method.py).
## Reproduction instructions
Use Python 3, no dependencies; run the supplied method on the reference at x=1.
"""
RESPONSE = """# Response
## Response to objections
The endpoint correction is consequential; the original bound was too strong.
## Revised claim
Only error below 0.2 is supported for this finite parameter.
## Sources and artifacts
[Targeted calculation](reference.csv) and [method](method.py).
## Reproduction instructions
Python 3; compare the saved correction with 0.2 at x=1.
"""


def check(outcome='objection'):
    return f"""# Independent check
Disposition: {outcome}
## Claim and scope
Finite x=1 comparison against the submitted evidence version only.
## Independent approach
Reconstruct the error from a separate subtraction, not the leading approximation.
## Observations
Reference minus leading estimate is 0.1, above the original 0.05 bound.
## Objections and limitations
The approximation omits a consequential endpoint correction. A targeted endpoint
sensitivity test should determine whether the revised bound applies beyond x=1.
## Reproduction or analytical evidence
Python 3: subtract the reference and estimate. [Saved subtraction](check.csv).
"""


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.CollaborationTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.project = self.case.project
        self.verifiers = []
        self.final_outcome = 'checked'
        self.close = False
        self.pause_phase = None
        self.bad_draft = False
        self.backend_failure = False
        self.human_report = False
        self.changed_initial_artifact = None
        self.ack_delay = 0
        self.prompt_handoffs = False

    def setup_exchange(self):
        self.assertEqual(self.case.start(), 0)
        self.state = self.case.state()
        self.coordinator = collaboration.Coordinator(self.project, self.state, isolation.Config())
        self.coordinator.begin_interval()
        primary = self.state['tasks']['primary']
        self.view = collaboration.TaskState(self.coordinator, primary)
        _, control, response = workspace.control_paths(self.project, self.view)
        self.config = isolation.Config(control=control, response=response, drafts=control.parent / 'drafts')
        self.runtime = {'task': primary, 'view': self.view, 'config': self.config}
        self.coordinator.running = {'primary': self.runtime}
        self.case.draft(self.config, 'work/PACKET.md', PACKET)
        self.case.draft(self.config, 'work/RESPONSE.md', RESPONSE)
        self.case.draft(self.config, 'work/CLOSE.md', '# Closure\nThe finite budget cannot settle endpoint sensitivity.')
        (self.project / 'work/method.py').write_text('print(2.0 - 1.9)\n')

    def request(self, **kwargs):
        request = {**workspace.owner_fields(self.view), 'task_id': 'primary',
                   'nonce': uuid.uuid4().hex, 'parent_task': 'primary', **kwargs}
        workspace.atomic_text(self.config.response / 'delegation.json', json.dumps(request))
        with patch.object(self.coordinator, 'launch') as launch:
            self.coordinator.accept_assignment(self.runtime)
        return workspace.read_control(self.config.control / 'delegation-ack.json'), launch

    def admit(self):
        ack, launch = self.request(operation='verify', assignment='work/PACKET.md')
        self.assertTrue(ack['accepted'], ack)
        task = self.state['tasks'][ack['task_id']]
        launch.assert_called_once_with(task)
        return task

    def deliver(self, task, outcome='objection'):
        record = task['verification']
        path = 'REEXAMINATION.md' if record['phase'] == 'reexamination' else 'CHECK.md'
        (self.project / task['workspace'] / path).write_text(check(outcome))
        (self.project / task['workspace'] / 'check.csv').write_text('error\n0.1\n')
        task['status'] = verification.deliver(self.project, task)
        self.coordinator.save()

    def test_frozen_packet_separate_identity_version_and_explicit_dependencies(self):
        self.setup_exchange()
        task = self.admit()
        self.assertEqual(task['role'], 'verifier')
        self.assertEqual(task['parent_task'], 'primary')
        self.assertNotEqual(task['workspace'], self.state['tasks']['primary']['workspace'])
        packet = task['verification']['initial']
        self.assertEqual({e['source'] for e in packet['evidence']},
                         {'work/PACKET.md', 'work/reference.csv', 'work/method.py'})
        copied = self.project / next(e['path'] for e in packet['evidence'] if e['source'] == 'work/method.py')
        (self.project / 'work/method.py').write_text('raise RuntimeError("changed original")')
        self.assertEqual(copied.read_text(), 'print(2.0 - 1.9)\n')
        self.assertIn('/inputs/initial/files/work/reference.csv', (self.project / packet['packet']).read_text())
        verification.check_unchanged(self.project, task)
        self.assertNotIn('.research_pipeline', json.dumps(packet))
        ack, launch = self.request(operation='verify', assignment='work/PACKET.md')
        self.assertEqual(ack['task_id'], task['task_id'])
        launch.assert_not_called()
        self.assertEqual(len([t for t in self.state['tasks'].values() if t['role'] == 'verifier']), 1)

    def test_bounded_response_retains_opposing_arguments_and_targeted_test(self):
        self.setup_exchange()
        task = self.admit()
        self.deliver(task)
        self.assertEqual(task['status'], 'awaiting_response')
        initial = (self.project / task['verification']['initial_check']).read_bytes()
        self.assertTrue(self.coordinator.has_slot())
        ack, _ = self.request(operation='respond', target=task['task_id'], response='work/RESPONSE.md')
        self.assertTrue(ack['accepted'], ack)
        self.assertTrue(task['verification']['response_committed'])
        self.assertEqual(task['verification']['exchange_limit'], 1)
        accepted = json.dumps(task['verification']['response'])
        ack, launch = self.request(operation='respond', target=task['task_id'], response='work/RESPONSE.md')
        self.assertTrue(ack['accepted'])
        launch.assert_not_called()
        self.assertEqual(json.dumps(task['verification']['response']), accepted)
        task['status'] = 'failed'
        ack, launch = self.request(operation='respond', target=task['task_id'], response='work/RESPONSE.md')
        self.assertTrue(ack['accepted'], ack)
        launch.assert_called_once_with(task)
        self.assertEqual(json.dumps(task['verification']['response']), accepted)
        ack, _ = self.request(operation='respond', target=task['task_id'], response='work/PACKET.md')
        self.assertFalse(ack['accepted'])
        self.deliver(task, 'objection')
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['verification']['disposition'], 'disputed')
        self.assertEqual((self.project / task['verification']['initial_check']).read_bytes(), initial)
        self.assertIn('targeted endpoint', (self.project / task['verification']['final_check']).read_text())
        self.assertIn('original bound was too strong', (self.project / task['verification']['response']['packet']).read_text())
        ack, launch = self.request(operation='respond', target=task['task_id'], response='work/RESPONSE.md')
        self.assertFalse(ack['accepted'])
        self.assertIn('cannot reopen', ack['error'])
        launch.assert_not_called()
        collaboration.validate_state(self.state, self.project)

    def test_capacity_refusal_consumes_no_response_and_close_needs_no_slot(self):
        self.setup_exchange()
        task = self.admit()
        self.deliver(task)
        self.coordinator.running['occupied'] = self.runtime
        ack, launch = self.request(operation='respond', target=task['task_id'], response='work/RESPONSE.md')
        self.assertFalse(ack['accepted'])
        self.assertFalse(task['verification']['response_committed'])
        self.assertFalse((self.project / task['workspace'] / 'inputs/response').exists())
        launch.assert_not_called()
        ack, launch = self.request(operation='close', target=task['task_id'], reason='work/CLOSE.md')
        self.assertTrue(ack['accepted'], ack)
        launch.assert_not_called()
        self.assertEqual(task['verification']['disposition'], 'disputed')
        self.assertIn('independent objection', (self.project / task['verification']['closure']).read_text())

    def test_changed_packets_reports_and_protected_publication_require_reassessment(self):
        self.setup_exchange()
        task = self.admit()
        self.deliver(task)
        drafts = self.project / '.research_pipeline/verifier-drafts'
        config = isolation.Config(drafts=drafts)
        for path in (task['verification']['initial_check'], task['assignment'],
                     task['verification']['initial']['packet'], task['workspace'] + '/inputs/new.md'):
            self.case.draft(config, path, '# Replacement')
            with self.assertRaisesRegex(workspace.InputError, 'Invalid scientific draft destination'):
                workspace.publish_drafts(self.project, drafts, {}, [], task['task_id'], workspace.protected_reports(task))
            (drafts / path).unlink()
        report = self.project / task['verification']['initial_check']
        report.write_text('# Human objection clarification')
        ack, launch = self.request(operation='respond', target=task['task_id'], response='work/RESPONSE.md')
        self.assertFalse(ack['accepted'])
        self.assertIn('reassessment', ack['error'])
        launch.assert_not_called()
        self.assertEqual(report.read_text(), '# Human objection clarification')
        packet = self.project / task['verification']['initial']['packet']
        packet.write_text('# Changed packet')
        with self.assertRaisesRegex(workspace.InputError, 'evidence changed'):
            verification.check_unchanged(self.project, task)

    def test_accepted_report_tracks_linked_code_data_and_markdown_through_integration(self):
        self.setup_exchange()
        task = self.admit()
        root = self.project / task['workspace']
        (root / 'check.csv').write_text('error\n0.1\n')
        (root / 'check.py').write_text('print(2.0 - 1.9)\n')
        (root / 'reasoning.md').write_text('# Independent subtraction\nThe correction exceeds 0.05.')
        (root / 'CHECK.md').write_text(check('checked') +
            '\n[Code](check.py) and [reasoning](reasoning.md).')
        task['status'] = verification.deliver(self.project, task)
        self.coordinator.save()
        saved = cli.load_state(self.project)['tasks'][task['task_id']]
        evidence = saved['verification']['initial_check_artifacts']
        self.assertEqual(set(evidence), {f"{task['workspace']}/{name}"
                                        for name in ('check.csv', 'check.py', 'reasoning.md')})
        verification.check_unchanged(self.project, saved)
        for rel in evidence:
            with self.subTest(artifact=rel):
                artifact = self.project / rel
                original = artifact.read_bytes()
                artifact.write_text('replaced check evidence')
                with self.assertRaisesRegex(workspace.InputError, 'artifact changed or missing'):
                    verification.check_unchanged(self.project, saved)
                failures = self.coordinator.validate_integration()
                self.assertTrue(any(rel in failure and 'reassessment required' in failure for failure in failures))
                artifact.write_bytes(original)
        verification.check_unchanged(self.project, saved)

    def test_bad_packet_and_wrong_owner_admission(self):
        self.setup_exchange()
        for link in ('../.research_pipeline/run.json', '../../host-private', 'missing.csv', 'pipe', 'symlink'):
            if link == 'pipe':
                import os
                os.mkfifo(self.project / 'work/pipe')
            if link == 'symlink':
                (self.project / 'work/symlink').symlink_to(self.project / 'work/reference.csv')
            self.case.draft(self.config, 'work/BAD.md', PACKET.replace('reference.csv', link))
            ack, launch = self.request(operation='verify', assignment='work/BAD.md')
            self.assertFalse(ack['accepted'], link)
            launch.assert_not_called()
        self.case.draft(self.config, 'work/NOTE.md', '# Note\n[Private dependency](UNSUPPLIED.md)')
        self.case.draft(self.config, 'work/UNSUPPLIED.md', '# Private dependency')
        self.case.draft(self.config, 'work/BAD.md', PACKET.replace('[Reference](reference.csv)', '[Note](NOTE.md)'))
        ack, _ = self.request(operation='verify', assignment='work/BAD.md')
        self.assertIn('explicitly', ack['error'])
        task = self.admit()
        ack, _ = self.request(operation='verify', assignment='work/PACKET.md', parent_task=task['task_id'])
        self.assertFalse(ack['accepted'])
        ack, _ = self.request(operation='verify', assignment='work/PACKET.md', ownership_nonce=uuid.uuid4().hex)
        self.assertFalse(ack['accepted'])
        child = next(t for t in self.state['tasks'].values() if t['role'] == 'researcher')
        ack, _ = self.request(operation='respond', target=child['task_id'], response='work/RESPONSE.md')
        self.assertFalse(ack['accepted'])

    def test_malformed_or_inconclusive_reports_cannot_become_checked(self):
        self.setup_exchange()
        task = self.admit()
        (self.project / task['workspace'] / 'CHECK.md').write_text('Disposition: checked\nlooks fine')
        with self.assertRaisesRegex(workspace.InputError, 'Missing substantive'):
            verification.deliver(self.project, task)
        self.assertIsNone(task['delivery'])
        (self.project / task['workspace'] / 'CHECK.md').write_text(check('checked'))
        with self.assertRaisesRegex(workspace.InputError, 'Missing verification check artifact'):
            verification.deliver(self.project, task)
        self.deliver(task, 'inconclusive')
        self.assertEqual(task['verification']['disposition'], 'preliminary')
        self.assertEqual(task['verification']['phase'], 'closed')

    def test_checked_initial_result_closes_without_manufacturing_a_response(self):
        self.setup_exchange()
        self.case.draft(self.config, 'work/PACKET.md', PACKET.replace('0.05', '0.2'))
        task = self.admit()
        root = self.project / task['workspace']
        (root / 'check.csv').write_text('error\n0.1\n')
        (root / 'CHECK.md').write_text(
            check('checked').replace('above the original 0.05 bound', 'below the proposed 0.2 bound')
            .replace('The approximation omits a consequential endpoint correction.',
                     'The proposed bound includes the endpoint correction.'))
        task['status'] = verification.deliver(self.project, task)
        self.coordinator.save()
        accepted = json.dumps(task['verification'], sort_keys=True)
        report = (root / 'CHECK.md').read_bytes()
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['verification']['phase'], 'closed')
        self.assertEqual(task['verification']['disposition'], 'checked')
        ack, launch = self.request(operation='respond', target=task['task_id'],
                                   response='work/RESPONSE.md')
        self.assertFalse(ack['accepted'])
        self.assertIn('cannot reopen', ack['error'])
        launch.assert_not_called()
        self.assertEqual(json.dumps(task['verification'], sort_keys=True), accepted)
        self.assertEqual((root / 'CHECK.md').read_bytes(), report)
        self.assertFalse((root / 'inputs/response').exists())
        verification.check_unchanged(self.project, task)

    def test_changing_evidence_during_copy_is_rejected_and_identical_uncommitted_packet_recovers(self):
        self.setup_exchange()
        original = verification.read_bytes
        changed = False
        def read(path, deadline):
            nonlocal changed
            data = original(path, deadline)
            if path.name == 'reference.csv' and not changed:
                changed = True
                path.write_text('x,value\n1,changed\n')
            return data
        with patch.object(verification, 'read_bytes', side_effect=read):
            ack, launch = self.request(operation='verify', assignment='work/PACKET.md')
        self.assertFalse(ack['accepted'])
        self.assertIn('changed during copying', ack['error'])
        launch.assert_not_called()
        task = self.admit()
        self.deliver(task)
        # Simulate copying a response immediately before a controller failure
        # that prevented acceptance from being saved. Identical admission is safe.
        destination = task['workspace'] + '/inputs/response'
        packet, _ = verification.freeze(self.project, 'work/RESPONSE.md', self.config.drafts,
                                        destination, verification.RESPONSE_FIELDS, self.coordinator.deadline)
        ack, _ = self.request(operation='respond', target=task['task_id'], response='work/RESPONSE.md')
        self.assertTrue(ack['accepted'], ack)
        self.assertEqual(task['verification']['response'], packet)

    def test_waiting_verifier_stays_stopped_on_resume_and_pending_rollover_retains_slot(self):
        self.setup_exchange()
        task = self.admit()
        self.deliver(task)
        seen = []
        # Exercise real resume selection without running another scientific backend.
        def launch(candidate):
            seen.append(candidate['task_id'])
            candidate['status'] = 'completed'
        self.coordinator.running = {}
        with patch.object(self.coordinator, 'launch', side_effect=launch):
            self.coordinator.run()
        self.assertNotIn(task['task_id'], seen)
        self.assertEqual(task['verification']['phase'], 'awaiting_response')
        self.coordinator.running = {'primary': self.runtime}
        task['status'] = 'rolling_over'
        self.assertFalse(self.coordinator.has_slot())
        self.assertTrue(self.coordinator.has_slot(task['task_id']))

    def test_changed_originals_do_not_inherit_checked_version_and_integration_is_required(self):
        self.setup_exchange()
        task = self.admit()
        self.deliver(task, 'checked')
        (self.project / 'work/PACKET.md').write_text(PACKET)
        report = self.project / 'outputs/REPORT.md'
        original = report.read_text()
        self.assertTrue(any(task['task_id'] in f for f in self.coordinator.validate_integration()))
        link = task['verification']['initial_check']
        report.write_text(original + f'\nChecked scope x=1, assumptions and uncertainty retained; '
                          f'no objection. [Check](../{link})')
        self.assertEqual(self.coordinator.validate_integration(), [])
        (self.project / 'work/reference.csv').write_text('x,value\n1,3\n')
        self.assertTrue(any(task['task_id'] in f for f in self.coordinator.validate_integration()))
        report.write_text(report.read_text() + '\nThe checked version is the copied evidence; changed original data remain preliminary.')
        self.assertEqual(self.coordinator.validate_integration(), [])
        self.assertIn('work/reference.csv', task['verification']['changed_originals'])

    def test_controller_killed_after_response_acceptance_preserves_allowance_and_recovers_science(self):
        script = r"""
import os, signal, sys
from pathlib import Path
from unittest.mock import patch
from tests.test_verification import VerificationTests
from research_pipeline import collaboration
case = VerificationTests()
case.setUp()
case.project = case.case.project = Path(sys.argv[1])
launch = collaboration.Coordinator.launch
def crash(self, task):
    if task['role'] == 'verifier' and task['verification']['phase'] == 'reexamination':
        saved = case.case.state()['tasks'][task['task_id']]
        assert saved['verification']['response_committed']
        assert saved['verification']['response']['evidence']
        os.kill(os.getpid(), signal.SIGKILL)
    return launch(self, task)
with patch.object(collaboration.Coordinator, 'launch', crash):
    case.start()
"""
        process = subprocess.run([sys.executable, '-c', script, str(self.project)],
                                 capture_output=True, timeout=5)
        self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
        state = cli.load_state(self.project)
        task = next(t for t in state['tasks'].values() if t['role'] == 'verifier')
        accepted = json.dumps(task['verification'], sort_keys=True)
        stopped = []
        with patch.object(isolation, 'stop_service', side_effect=lambda unit: stopped.append(unit) or True):
            cli.recover_owner(self.project, state)
        self.assertEqual(json.dumps(task['verification'], sort_keys=True), accepted)
        verification.check_unchanged(self.project, task)
        self.assertTrue(state['cleanup_ok'])
        self.assertFalse(state['usage_complete'])
        self.assertTrue(stopped)
        self.assertFalse(state['owner_interval']['pending'])
        # A new owner can continue the SAME accepted phase; no second response exists.
        from types import SimpleNamespace
        self.case.services = [SimpleNamespace(task_id='primary') for _ in range(8)]
        self.case.project = self.project
        with self.backend(), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['resume', str(self.project)]), 0, self.case.state().get('reason'))
        resumed = self.case.state()
        final = resumed['tasks'][task['task_id']]
        self.assertEqual(final['verification']['response'], task['verification']['response'])
        self.assertEqual(final['verification']['exchange_limit'], 1)
        self.assertEqual(final['verification']['disposition'], 'checked')
        self.assertGreater(resumed['active_seconds'], state['active_seconds'])
        self.assertTrue(resumed['cleanup_ok'])

    @contextmanager
    def backend(self):
        """Reuse delegated rollover fixtures; add verifier and primary exchange behavior."""
        case, test = self.case, self
        with case.backend():
            service = isolation.RunningService
            class Verifier:
                def __init__(self, config, project, command, prompt, recorder, auth):
                    self.config, self.recorder = config, recorder
                    self.task_id, self.prompt = config.task_id, prompt
                    self.task = config.on_poll.__self__.view.task
                    self.phase = self.task['verification']['phase']
                    self.number = sum(v.phase == self.phase and v.task_id == self.task_id for v in test.verifiers)
                    self.result = isolation.ExecutionResult(0, cleanup_ok=True)
                    self.finished = False
                    self.request_seen_at = None
                    self.acknowledged_at = None
                    test.verifiers.append(self)
                    case.services.append(self)
                    recorder('stdout', (json.dumps({'type':'thread.started', 'thread_id': 'verifier-' + uuid.uuid4().hex})+'\n').encode())
                    recorder('stdout', b'{"type":"item.completed","item":{"type":"command_execution","exit_code":0}}\n')
                    recorder('stdout', b'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}\n')
                    assert config.frozen_inputs == (self.task['workspace'] + '/inputs',)
                    assert 'independently' in prompt.lower()
                    assert 'no independent verifier' not in prompt
                    assert 'Perform substantive analytical reasoning and a meaningful executable numerical calculation.' not in prompt
                    root = self.task['workspace']
                    data = 'reexamination.csv' if self.phase == 'reexamination' else 'check.csv'
                    if self.number:
                        assert 'Computed a reference and saved reusable data.' in prompt
                        assert (project / root / data).read_text() == 'error\n0.1\n'
                    (project / root / data).write_text('error\n0.1\n')
                    path = 'REEXAMINATION.md' if self.phase == 'reexamination' else 'CHECK.md'
                    text = check(test.final_outcome if self.phase == 'reexamination' else 'objection')
                    case.draft(config, root + '/' + path, text.replace('(check.csv)', f'({data})'))
                    handoff = fixtures.handoff(self.task_id, root + '/' + data)
                    if test.prompt_handoffs:
                        # Follow the final handoff checklist literally, as the live
                        # verifier did. Do not silently add fields from the fixture.
                        schema = prompt.split('fields/headings:\n', 1)[1].split(
                            '\nInclude substantive progress', 1)[0]
                        bodies = verification.sections(handoff, (
                            'Objective', 'Completed', 'Artifacts', 'Assumptions',
                            'Unresolved', 'Next action', 'Parent question',
                            'Interrupted computation', 'Resume or reconsider'))
                        handoff = '\n'.join(
                            field + ('\n' + bodies[field[3:]] + '\n' if field.startswith('## ') else '')
                            for field in schema.splitlines())
                    case.draft(config, f'handoffs/{self.task_id}.md', handoff)
                    if test.bad_draft and self.phase == 'reexamination':
                        case.draft(config, root + '/CHECK.md', '# Replace original objection')

                def poll(self):
                    reason = self.config.on_poll()
                    request = workspace.read_control(self.config.control / 'request.json')
                    if request:
                        if self.request_seen_at is None:
                            self.request_seen_at = case.clock
                        if case.clock - self.request_seen_at < test.ack_delay:
                            return bool(reason)
                        workspace.atomic_text(self.config.response / 'ready.json', json.dumps({**request, 'readiness_nonce':uuid.uuid4().hex}))
                        self.config.on_poll()
                        ack = workspace.read_control(self.config.control / 'ack.json')
                        if ack and ack.get('accepted'):
                            self.acknowledged_at = case.clock
                        return bool(ack and ack.get('accepted')) or bool(reason)
                    if test.pause_phase == self.phase and not self.number:
                        state = case.state()
                        _, control, _ = workspace.control_paths(test.project, state)
                        workspace.atomic_text(control / 'request.json', json.dumps({'version':1, **workspace.owner_fields(state),
                            'request_id':uuid.uuid4().hex, 'reason':'pause'}))
                    return test.prompt_handoffs or bool(self.number)

                def finish(self):
                    self.finished = True
                    if test.changed_initial_artifact and self.phase == 'reexamination' and self.number:
                        artifact = test.project / self.task['workspace'] / 'check.csv'
                        if test.changed_initial_artifact == 'overwrite':
                            artifact.write_text('error\n0.0\n')
                        else:
                            artifact.unlink()
                    if test.human_report and self.phase == 'initial' and self.number:
                        (test.project / self.task['workspace'] / 'CHECK.md').write_text(
                            check('checked') + '\nHuman clarification requires reassessment.')
                    if test.backend_failure and self.number:
                        self.result.returncode = 1
                        self.result.error = 'Independent reproduction backend failed'
                    return self.result

            def launch(config, project, command, prompt, recorder, auth):
                view = config.on_poll.__self__.view
                if view['role'] == 'verifier':
                    return Verifier(config, project, command, prompt, recorder, auth)
                instance = service(config, project, command, prompt, recorder, auth)
                if config.task_id != 'primary':
                    return instance
                case.draft(config, 'work/PACKET.md', PACKET)
                case.draft(config, 'work/RESPONSE.md', RESPONSE)
                case.draft(config, 'work/CLOSE.md', '# Closure\nEndpoint sensitivity remains unresolved within this budget.')
                (project / 'work/method.py').write_text('print(2.0 - 1.9)\n')
                original_poll = instance.poll
                def poll():
                    ended = original_poll()
                    if workspace.read_control(config.control / 'request.json'):
                        return ended
                    state = case.state()
                    child = next((t for t in state['tasks'].values() if t['role'] == 'researcher'), None)
                    task = next((t for t in state['tasks'].values() if t['role'] == 'verifier'), None)
                    operation = None
                    if task is None and child and child['status'] == 'completed':
                        operation = {'operation':'verify', 'assignment':'work/PACKET.md', 'parent_task':child['task_id']}
                    elif task and task['status'] == 'awaiting_response':
                        operation = ({'operation':'close', 'target':task['task_id'], 'reason':'work/CLOSE.md'} if test.close else
                                     {'operation':'respond', 'target':task['task_id'], 'response':'work/RESPONSE.md'})
                    elif task and task['status'] == 'completed':
                        record = task['verification']
                        refs = [child['delivery']['result'], record['initial_check']]
                        refs += [record[key] for key in ('final_check','closure') if record.get(key)]
                        if record['response']:
                            refs.append(record['response']['packet'])
                        links = ' '.join(f'[Evidence](../{r})' for r in refs)
                        case.draft(config, 'outputs/REPORT.md',
                            f'# {record["disposition"]} synthesis\nPreliminary exploration remains. '
                            'Scope is x=1; assumptions and uncertainty limit applicability. '
                            'The objection superseded the earlier 0.05 conclusion; only the reviewed version is checked. '
                            + links + ' [Reference](../work/reference.csv)')
                        return True
                    elif task and task['status'] in ('failed', 'incomplete', 'interrupted'):
                        return True
                    if operation:
                        previous = workspace.read_control(config.response / 'delegation.json')
                        ack = workspace.read_control(config.control / 'delegation-ack.json')
                        if not previous or ack and ack['nonce'] == previous['nonce']:
                            workspace.atomic_text(config.response / 'delegation.json', json.dumps({**workspace.owner_fields(view),
                                'task_id':'primary', 'nonce':uuid.uuid4().hex, **operation}))
                    return False
                instance.poll = poll
                return instance
            with patch.object(isolation, 'RunningService', side_effect=launch):
                yield

    def start(self, delegated_seconds='16', wall_seconds='100', primary_seconds='300'):
        with self.backend(), redirect_stdout(io.StringIO()):
            return cli.main(['start', str(self.project), '--max-agents','2', '--wall-seconds', wall_seconds,
                             '--memory-mib','512', '--max-tasks','64', '--delegated-session-seconds', delegated_seconds,
                             '--primary-session-seconds', primary_seconds])

    def test_delayed_verifier_handoff_continues_both_examinations_within_original_grant(self):
        self.ack_delay = 18
        self.assertEqual(self.start(delegated_seconds='80', wall_seconds='500',
                                    primary_seconds='600'), 0, self.case.state())
        state = self.case.state()
        self.assertEqual([v.phase for v in self.verifiers],
                         ['initial', 'initial', 'reexamination', 'reexamination'])
        for verifier in self.verifiers[::2]:
            self.assertEqual(verifier.acknowledged_at - verifier.request_seen_at, 18)
            self.assertLess(verifier.acknowledged_at, verifier.config.deadline)
        task = next(t for t in state['tasks'].values() if t['role'] == 'verifier')
        self.assertEqual(task['verification']['disposition'], 'checked')
        self.assertEqual(task['verification']['exchange_limit'], 1)
        self.assertEqual(task['integration'], ['outputs/REPORT.md'])
        self.assertEqual(state['usage_totals'], {'input_tokens': 70, 'output_tokens': 14})
        self.assertEqual(state['remaining_active_seconds'], 500 - state['active_seconds'])
        self.assertTrue(state['cleanup_ok'])

    def test_initial_and_reexamination_rollover_keep_same_task_and_cumulative_limits(self):
        self.assertEqual(self.start(), 0, self.case.state())
        state = self.case.state()
        task = next(t for t in state['tasks'].values() if t['role'] == 'verifier')
        self.assertEqual(task['verification']['disposition'], 'checked')
        self.assertEqual([v.phase for v in self.verifiers], ['initial','initial','reexamination','reexamination'])
        self.assertEqual(len({v.task_id for v in self.verifiers}), 1)
        self.assertEqual(len({s['native_session_id'] for s in state['sessions']}), 7)
        self.assertEqual(task['integration'], ['outputs/REPORT.md'])
        self.assertEqual(state['usage_totals'], {'input_tokens':70,'output_tokens':14})
        self.assertEqual(state['remaining_active_seconds'], 100 - state['active_seconds'])
        self.assertTrue(all(s.config.memory_mib == 256 for s in self.case.services))
        self.assertTrue(all(s.finished for s in self.case.services))
        self.assertTrue(any(n == 4 for _, n in self.case.parent_progress))
        self.assertTrue(any(n == 7 for _, n in self.case.parent_progress))
        self.assertTrue(state['cleanup_ok'])
        self.assertNotIn('backend.jsonl', self.verifiers[-1].prompt)
        self.assertIn('response_committed', self.verifiers[-1].prompt)
        report = self.project / 'outputs/REPORT.md'
        report.write_text(report.read_text().replace('Preliminary exploration remains. ', ''))
        self.assertEqual(workspace.validate_deliverables(self.project, labels=('checked', 'disputed')), [])
        coordinator = collaboration.Coordinator(self.project, state, isolation.Config())
        self.assertEqual(coordinator.validate_integration(), [])
        initial = task['verification']['initial_check_artifacts']
        final = task['verification']['final_check_artifacts']
        self.assertEqual(set(initial), {task['workspace'] + '/check.csv'})
        self.assertEqual(set(final), {task['workspace'] + '/reexamination.csv'})
        (self.project / next(iter(final))).write_text('altered final evidence')
        self.assertTrue(any('reexamination.csv' in failure and 'reassessment required' in failure
                            for failure in coordinator.validate_integration()))

    def test_prompt_handoff_checklist_delivers_both_phases_without_repair_context(self):
        self.prompt_handoffs = True
        self.assertEqual(self.start(), 0, self.case.state())
        state = self.case.state()
        self.assertEqual([v.phase for v in self.verifiers], ['initial', 'reexamination'])
        task = next(t for t in state['tasks'].values() if t['role'] == 'verifier')
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['verification']['disposition'], 'checked')
        self.assertTrue(task['verification']['response_committed'])
        self.assertEqual(task['verification']['exchange_limit'], 1)
        self.assertIn('Disposition: objection',
                      (self.project / task['verification']['initial_check']).read_text())
        self.assertEqual(task['integration'], ['outputs/REPORT.md'])
        sessions = [s for s in state['sessions'] if s['role'] == 'verifier']
        self.assertEqual(len({s['native_session_id'] for s in sessions}), 2)
        for session in sessions:
            self.assertNotIn('checkpoint_error', session)
            self.assertEqual(session['checkpoint_id'], session['activation_id'])
            saved = (self.project / session['logs'] / 'handoff.md').read_text()
            workspace.validate_handoff(self.project, saved, task_id=task['task_id'])
        verification.check_unchanged(self.project, task)
        self.assertTrue(state['cleanup_ok'])

    def test_disputed_exchange_and_declined_exchange_allow_parent_completion(self):
        self.final_outcome = 'objection'
        self.assertEqual(self.start(), 0, self.case.state())
        task = next(t for t in self.case.state()['tasks'].values() if t['role'] == 'verifier')
        self.assertEqual(task['verification']['disposition'], 'disputed')
        self.assertIn('earlier 0.05', (self.project / 'outputs/REPORT.md').read_text())

    def test_close_awaiting_objection_without_reexamination(self):
        self.close = True
        self.assertEqual(self.start(), 0, self.case.state())
        task = next(t for t in self.case.state()['tasks'].values() if t['role'] == 'verifier')
        self.assertEqual(task['verification']['disposition'], 'disputed')
        self.assertFalse(task['verification']['response_committed'])
        self.assertEqual(len(self.verifiers), 2)

    def test_pause_resume_reexamination_preserves_accepted_response_and_original_check(self):
        self.pause_phase = 'reexamination'
        self.assertEqual(self.start(), 0, self.case.state())
        state = self.case.state()
        task = next(t for t in state['tasks'].values() if t['role'] == 'verifier')
        initial = (self.project / task['verification']['initial_check']).read_bytes()
        self.assertEqual(state['state'], 'paused')
        self.assertTrue(task['verification']['response_committed'])
        self.assertTrue(all(s.finished for s in self.case.services))
        self.pause_phase = None
        with self.backend(), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['resume', str(self.project)]), 0, self.case.state())
        resumed = self.case.state()
        self.assertEqual(resumed['tasks'][task['task_id']]['verification']['exchange_limit'], 1)
        self.assertEqual(resumed['limits'], state['limits'])
        self.assertGreater(resumed['active_seconds'], state['active_seconds'])
        self.assertEqual((self.project / task['verification']['initial_check']).read_bytes(), initial)
        self.assertTrue(resumed['cleanup_ok'])

    def test_reexamination_cannot_replace_original_objection(self):
        self.bad_draft = True
        self.assertEqual(self.start(), 4)
        task = next(t for t in self.case.state()['tasks'].values() if t['role'] == 'verifier')
        self.assertIn('Invalid scientific draft destination', task['checkpoint_error'])
        self.assertIn('endpoint correction', (self.project / task['verification']['initial_check']).read_text())
        self.assertEqual(len(self.verifiers), 3)
        self.assertTrue(self.case.state()['cleanup_ok'])

    def assert_changed_initial_artifact_refuses_completion(self, operation):
        self.changed_initial_artifact = operation
        self.assertEqual(self.start(), 4)
        state = self.case.state()
        task = next(t for t in state['tasks'].values() if t['role'] == 'verifier')
        record = task['verification']
        self.assertEqual([v.phase for v in self.verifiers],
                         ['initial', 'initial', 'reexamination', 'reexamination'])
        self.assertEqual(task['status'], 'incomplete')
        self.assertEqual(record['disposition'], 'disputed')
        self.assertIsNone(record['final_check'])
        self.assertIn('artifact changed or missing', task['checkpoint_error'])
        self.assertIn('reassessment required', task['checkpoint_error'])
        self.assertIn('endpoint correction', (self.project / record['initial_check']).read_text())
        self.assertTrue(record['initial_check_artifacts'])
        self.assertTrue(state['cleanup_ok'])

    def test_reexamination_overwriting_initial_check_data_refuses_completion(self):
        self.assert_changed_initial_artifact_refuses_completion('overwrite')

    def test_reexamination_deleting_initial_check_data_refuses_completion(self):
        self.assert_changed_initial_artifact_refuses_completion('delete')

    def test_full_pause_during_initial_check_preserves_unfinished_phase_and_handoff(self):
        self.pause_phase = 'initial'
        self.assertEqual(self.start(), 0, self.case.state().get('reason'))
        state = self.case.state()
        task = next(t for t in state['tasks'].values() if t['role'] == 'verifier')
        self.assertEqual(state['state'], 'paused')
        self.assertEqual(task['verification']['phase'], 'initial')
        self.assertFalse(task['verification']['response_committed'])
        self.assertIsNone(task['delivery'])
        self.assertTrue((self.project / workspace.handoff_path(task['task_id'])).exists())
        self.assertEqual(len(self.verifiers), 1)
        self.assertTrue(all(s.finished for s in self.case.services))
        self.assertTrue(state['cleanup_ok'])

    def test_backend_failure_with_saved_check_cannot_deliver_checked_outcome(self):
        self.backend_failure = True
        self.assertEqual(self.start(), 4)
        task = next(t for t in self.case.state()['tasks'].values() if t['role'] == 'verifier')
        self.assertEqual(task['status'], 'failed')
        self.assertEqual(task['verification']['disposition'], 'preliminary')
        self.assertIsNone(task['delivery'])
        self.assertTrue((self.project / task['workspace'] / 'check.csv').is_file())
        self.assertTrue(self.case.state()['cleanup_ok'])

    def test_concurrent_human_check_edit_is_preserved_without_silent_acceptance(self):
        self.human_report = True
        self.assertEqual(self.start(), 4)
        task = next(t for t in self.case.state()['tasks'].values() if t['role'] == 'verifier')
        self.assertEqual(task['status'], 'incomplete')
        self.assertIsNone(task['delivery'])
        self.assertIn('reassessment required', task['checkpoint_error'])
        self.assertIn('Human clarification', (self.project / task['workspace'] / 'CHECK.md').read_text())
        self.assertTrue(task['pending_reconciliation'])


if __name__ == '__main__':
    unittest.main()
