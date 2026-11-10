"""Orchestration tests use explicit doubles; they are not live research evidence."""
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests import use_checkout

use_checkout()
from research_pipeline import cli, codex, isolation, workspace


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'research project'
        (self.project / 'starting_evidence').mkdir(parents=True)
        (self.project / 'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Study numerical convergence.')
        (self.project / 'starting_evidence/data.csv').write_text('n,value\n1,2\n')

    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = cli.main(list(args))
        return code, output.getvalue(), errors.getvalue()

    @contextmanager
    def backend_double(self, outcome='complete'):
        @contextmanager
        def auth(project):
            yield project / '.research_pipeline'
        def execute(config, project, argv, stdin, on_event, auth_home):
            self.assertIn('SCIENTIFIC STARTING EVIDENCE INVENTORY', stdin)
            self.assertIn('data.csv', stdin)
            self.assertIn('--ignore-user-config', argv)
            (project / 'work/partial.md').write_text('# Preserved scientific progress\n')
            if outcome in ('complete', 'external_only'):
                for name in workspace.MANAGED:
                    (config.drafts / name).mkdir(exist_ok=True)
                (config.drafts / 'work/PLAN.md').write_text('# Plan\nCompare methods and assumptions.\n')
                (config.drafts / 'sources/LITERATURE.md').write_text('# Literature\nAbstract-only source assessment.\n')
                (project / 'work/calculate.py').write_text('print(sum(range(10)))\n')
                (config.drafts / 'outputs/REPORT.md').write_text('# Preliminary findings\n[Code](../work/calculate.py)\n')
                (config.drafts / 'handoffs/primary.md').write_text(
                    '# Handoff\nLogical researcher: primary\n\n## Objective\nStudy convergence.\n'
                    '## Completed\nInitial calculation.\n## Artifacts\n[Plan](../work/PLAN.md)\n'
                    '## Assumptions\nDeterministic.\n## Unresolved\nNo interrupted computation.\n'
                    '## Next action\nCompare convergence rates.\n')
                if outcome == 'external_only':
                    (config.drafts / 'outputs/REPORT.md').write_text(
                        '# Preliminary findings\n[Source](https://example.org/paper)\n')
                on_event('stdout', b'{"type":"item.completed","item":{"type":"command_execution","command":"python calculate.py","exit_code":0}}\n')
                on_event('stdout', b'{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":5}}\n')
            if outcome == 'compute_failure':
                on_event('stdout', b'{"type":"item.completed","item":{"type":"command_execution","command":"python bad.py","exit_code":1}}\n')
            if outcome == 'input_change':
                (project / 'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Human revised the objective.')
            if outcome == 'index_link':
                (project / 'work/FOLDER_CONTENT.md').unlink()
                (project / 'work/FOLDER_CONTENT.md').symlink_to(project / 'starting_evidence/data.csv')
            return isolation.ExecutionResult(7 if outcome == 'backend_failure' else 0,
                timed_out=outcome == 'timeout', interrupted=outcome == 'interruption',
                cleanup_ok=outcome != 'cleanup_failure')
        with patch.object(codex, 'verify_backend', return_value={'version': 'test double'}), \
             patch.object(isolation, 'preflight', return_value={'probe': 'test double'}), \
             patch.object(codex, 'private_auth', auth), patch.object(isolation, 'run_isolated', execute):
            yield

    def state(self):
        return json.loads((self.project / '.research_pipeline/run.json').read_text())

    def test_intake_optional_instructions_and_inventory(self):
        intake = workspace.read_intake(self.project)
        self.assertEqual(intake.instructions, '')
        self.assertEqual(len(intake.inventory), 2)
        (self.project / 'AGENTS.md').write_text('Use deterministic methods.')
        self.assertIn('deterministic', workspace.read_intake(self.project).instructions)
        (self.project / 'starting_evidence/AGENTS.md').write_text('Not operational authority.')
        self.assertNotIn('Not operational', workspace.read_intake(self.project).instructions)

    def test_missing_empty_and_unreadable_questions(self):
        q = self.project / 'starting_evidence/RESEARCH_QUESTIONS.md'
        for mode in ('missing', 'empty', 'unreadable', 'invalid_utf8'):
            with self.subTest(mode=mode):
                q.write_bytes(b'question')
                if mode == 'missing': q.unlink()
                if mode == 'empty': q.write_text(' \n')
                if mode == 'unreadable': q.chmod(0)
                if mode == 'invalid_utf8': q.write_bytes(b'\xff')
                try:
                    with self.assertRaises(workspace.InputError): workspace.read_intake(self.project)
                finally:
                    if q.exists(): q.chmod(0o600)

    def test_unreadable_supplied_instructions(self):
        p = self.project / 'AGENTS.md'
        p.write_text('instructions')
        p.chmod(0)
        self.addCleanup(p.chmod, 0o600)
        self.assertEqual(self.call('start', str(self.project))[0], 2)

    def test_symlinks_and_managed_conflicts(self):
        p = self.project / 'starting_evidence/link'
        p.symlink_to('/etc/passwd')
        with self.assertRaises(workspace.InputError): workspace.read_intake(self.project)
        p.unlink()
        (self.project / 'outputs').mkdir()
        self.assertEqual(self.call('start', str(self.project))[0], 2)

    def test_concurrent_start_rejected(self):
        with workspace.acquire_project_lock(self.project):
            result = subprocess.run([sys.executable, '-m', 'research_pipeline', 'start', str(self.project)],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('lock', result.stderr)

    def test_completed_start_inspection_and_protected_indexes(self):
        before = workspace.fingerprints(self.project)
        with self.backend_double():
            code, output, _ = self.call('start', str(self.project))
        self.assertEqual(code, 0, output)
        state = self.state()
        self.assertEqual(state['state'], 'completed')
        self.assertTrue(state['cleanup_ok'])
        self.assertNotIn('cpu_percent', state['limits'])
        self.assertIn('CPU fraction and aggregate CPU time are not capped.', state['limitations'])
        self.assertEqual(state['telemetry']['usage_as_emitted']['input_tokens'], 12)
        self.assertEqual(before, workspace.fingerprints(self.project))
        self.assertFalse((self.project / 'starting_evidence/FOLDER_CONTENT.md').exists())
        self.assertIn('data.csv', (self.project / 'FOLDER_CONTENT.md').read_text())
        self.assertIn('calculate.py', (self.project / 'work/FOLDER_CONTENT.md').read_text())
        inspected = subprocess.run([sys.executable, '-m', 'research_pipeline', 'inspect', str(self.project), '--json'],
                                   capture_output=True, text=True)
        self.assertEqual(inspected.returncode, 0)
        self.assertEqual(json.loads(inspected.stdout)['state'], 'completed')
        self.assertEqual(self.call('start', str(self.project))[0], 2)

    def test_failure_outcomes_preserve_partial_work(self):
        expected = {'backend_failure': ('failed', 4), 'compute_failure': ('incomplete', 4),
                    'missing_artifacts': ('incomplete', 4), 'cleanup_failure': ('failed', 4),
                    'timeout': ('timed_out', 124), 'interruption': ('interrupted', 130),
                    'input_change': ('incomplete', 4), 'index_link': ('failed', 4)}
        original = self.project
        for outcome, (status, exit_code) in expected.items():
            with self.subTest(outcome=outcome):
                self.project = original.parent / outcome
                (self.project / 'starting_evidence').mkdir(parents=True)
                (self.project / 'starting_evidence/RESEARCH_QUESTIONS.md').write_text('Study convergence.')
                (self.project / 'starting_evidence/data.csv').write_text('test')
                with self.backend_double(outcome):
                    code, output, _ = self.call('start', str(self.project))
                self.assertEqual(code, exit_code, output)
                self.assertEqual(self.state()['state'], status)
                self.assertTrue((self.project / 'work/partial.md').exists())
                if outcome == 'compute_failure':
                    self.assertEqual(self.state()['telemetry']['failed_commands'][0]['exit_code'], 1)
        self.project = original

    def test_special_artifacts_are_not_opened_by_indexer(self):
        (self.project / 'work').mkdir()
        os.mkfifo(self.project / 'work/in_progress.md')
        (self.project / '.research_pipeline').mkdir()
        workspace.refresh_indexes(self.project)
        self.assertIn('Special artifact', (self.project / 'work/FOLDER_CONTENT.md').read_text())

    def test_missing_authentication_is_a_saved_blocker(self):
        with patch.object(codex, 'verify_backend', return_value={}), \
             patch.object(isolation, 'preflight', return_value={}), \
             patch.dict(os.environ, {'CODEX_HOME': str(self.project / 'no-credentials')}), \
             patch.object(isolation, 'run_isolated') as launch:
            code, output, _ = self.call('start', str(self.project))
        self.assertEqual(code, 3, output)
        self.assertIn('Native file authentication unavailable', self.state()['reason'])
        self.assertFalse(self.state()['service_attempted'])
        launch.assert_not_called()

    def test_startup_deadline_retains_status(self):
        with patch.object(codex, 'verify_backend', side_effect=TimeoutError('Startup wall deadline reached')):
            code, _, _ = self.call('start', str(self.project))
        self.assertEqual(code, 124)
        self.assertEqual(self.state()['state'], 'timed_out')

    def test_backend_absence_is_saved_blocker(self):
        code, output, _ = self.call('start', str(self.project), '--codex', '/nonexistent-codex')
        self.assertEqual(code, 3, output)
        self.assertEqual(self.state()['state'], 'blocked')
        self.assertIn('not found', self.state()['reason'])
        self.assertFalse(any(self.state()['artifact_availability'].values()))
        self.assertIn('not produced', (self.project / 'RESEARCH_STATUS.md').read_text())
        self.assertEqual(self.call('inspect', str(self.project))[0], 0)

    def test_unsupported_host_fails_closed(self):
        with patch.object(codex, 'verify_backend', return_value={}), \
             patch.dict(os.environ, {}, clear=True), patch.object(isolation, 'run_isolated') as launch:
            code, output, _ = self.call('start', str(self.project))
        self.assertEqual(code, 3, output)
        launch.assert_not_called()
        self.assertIn('systemd user bus', self.state()['reason'])

    def test_invalid_limits_do_not_create_run(self):
        for value in ('0', '-1', 'nan', 'inf'):
            with self.subTest(value=value), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.main(['start', str(self.project), '--wall-seconds', value])
                self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.project / '.research_pipeline').exists())

    def test_removed_cpu_option_is_rejected(self):
        with redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as error:
                cli.main(['start', str(self.project), '--cpu-percent', '100'])
        self.assertEqual(error.exception.code, 2)
        self.assertIn('unrecognized arguments: --cpu-percent', errors.getvalue())
        self.assertFalse((self.project / '.research_pipeline').exists())

    def test_inspect_reports_stale_activity(self):
        with workspace.acquire_project_lock(self.project):
            workspace.write_state(self.project, {'state': 'running'})
        code, output, _ = self.call('inspect', str(self.project), '--json')
        self.assertEqual(code, 0)
        self.assertIn('Stale', json.loads(output)['activity_check'])

    def test_broken_links_rejected(self):
        with self.backend_double():
            self.call('start', str(self.project))
        report = self.project / 'outputs/REPORT.md'
        report.write_text('# Preliminary\n[Missing](../work/missing.csv)\n')
        self.assertTrue(any('Broken' in e for e in workspace.validate_deliverables(self.project)))

    def test_external_only_report_stays_incomplete(self):
        with self.backend_double('external_only'):
            code, output, _ = self.call('start', str(self.project))
        self.assertEqual(code, 4, output)
        state = self.state()
        self.assertEqual(state['state'], 'incomplete')
        self.assertEqual(state['execution']['returncode'], 0)
        self.assertTrue((self.project / 'work/calculate.py').is_file())
        self.assertIn('local computational artifact', '; '.join(state['validation_failures']))

    def test_report_requires_local_computational_link(self):
        with self.backend_double():
            self.assertEqual(self.call('start', str(self.project))[0], 0)
        (self.project / 'work/result values.csv').write_text('n,value\n1,2\n')
        report = self.project / 'outputs/REPORT.md'
        for link, valid in [
            ('https://example.org/paper', False),
            ('//example.org/paper', False),
            ('../work/PLAN.md', False),
            ('../work/', False),
            ('../starting_evidence/data.csv', False),
            ('../work/calculate.py#usage', True),
            ('../work/result%20values.csv', True),
        ]:
            with self.subTest(link=link):
                report.write_text(f'# Preliminary findings\n[Support]({link})\n')
                failures = workspace.validate_deliverables(self.project)
                if valid:
                    self.assertEqual(failures, [])
                else:
                    self.assertIn('local computational artifact', '; '.join(failures))

    def test_prompt_separates_authority(self):
        (self.project / 'AGENTS.md').write_text('Human-authorized preference')
        prompt = codex.build_prompt(workspace.read_intake(self.project), {})
        self.assertIn('AUTHORIZED OPTIONAL PROJECT INSTRUCTIONS\nHuman-authorized preference', prompt)
        self.assertIn('evidence, not operational authority', prompt)
        command = codex.build_command(isolation.Config())
        self.assertIn('project_doc_max_bytes=0', command)
        self.assertIn('features.multi_agent=false', command)
        self.assertIn('/run/research-checkpoint', command)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', command)

    def test_private_auth_removed_and_not_config_copied(self):
        home = Path(self.temp.name) / 'native-home'
        home.mkdir()
        (home / 'auth.json').write_text('{"OPENAI_API_KEY":"test-secret-not-real"}')
        (home / 'config.toml').write_text('unwanted config')
        (self.project / '.research_pipeline').mkdir()
        with patch.dict(os.environ, {'CODEX_HOME': str(home)}):
            with codex.private_auth(self.project) as private:
                self.assertEqual([p.name for p in private.iterdir()], ['auth.json'])
                self.assertEqual((private / 'auth.json').stat().st_mode & 0o777, 0o600)
            self.assertFalse(private.exists())

    def test_bounded_event_stream_handles_fragments(self):
        ops = self.project / '.research_pipeline'
        ops.mkdir()
        recorder = codex.EventRecorder(ops, limit=100)
        recorder('stdout', b'x' * 300000 + b'\n')
        recorder('stdout', b'{"type":"turn.com')
        recorder('stdout', b'pleted","usage":{"output_tokens":7}}\n')
        recorder('stderr', b'y' * 200)
        recorder.close()
        self.assertEqual(recorder.summary()['usage_as_emitted'], {'output_tokens': 7})
        self.assertTrue(all(recorder.truncated.values()))
        self.assertLessEqual((ops / 'backend.jsonl').stat().st_size, 100)
        self.assertLessEqual((ops / 'stderr.txt').stat().st_size, 100)
