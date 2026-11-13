"""Opt-in native scientific opposition; enabled missing prerequisites FAIL.

Agents author all science and terminal submissions. No injected quota, telemetry,
consensus, direct decision RPCs or alternative isolation path is used here.
"""
import asyncio
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from tests import use_checkout
use_checkout()
from tests.test_v0_l1_native import reserve_validation_output
from research_pipeline import collaboration, decisions, isolation, jobs, workspace


QUESTIONS = """# Public integration investigation

1. Derive the signed composite trapezoidal integration error for f(x)=x^2 on
   [0,1], state the sign convention and dependence on subdivision count, and
   corroborate the result computationally.
2. Assess what those computations establish about reliability for other smooth
   functions. Support the scope assessment with an independently checkable stress
   case, counterexample or justified limitation.
"""

INSTRUCTIONS = """This small public investigation exercises the scientific
decision path. Supply your own reasoning and conclusions; no expected answer or
verdict is supplied. Use the default allocation. No delegation is needed.

Primary: derive the result, run an admitted numerical computation, preserve
reproducible code/data and qualified conclusions with explicit evidence links.
Save a usable handoff. When results justify a terminal proposal, use the ordinary
propose_complete/propose_stop controls. Read the opponent's entire challenge
(the full text, regardless of its verdict) with control(history) and
control(read_history, parent="review"), following next_offset until null.
Respond substantively in saved Markdown, correct or investigate objections and
present renewed proposals whenever needed. Preserve objection dispositions.
After a delivered review and confirmed opponent retirement, only you may request
finalize_complete/finalize_stop with the current proposal version. Do not change
frozen supporting artifacts while awaiting review; new science requires a renewed
proposal. Scientific STOP requires your actual best recovery attempts and need for
human intervention; a test's operational bound is never a scientific rationale.

Opponent: inspect the EXACT current frozen packet via control(check/tasks).
Independently reconstruct consequential claims and run your own admitted numerical
countercheck or reproduction in your scoped workspace. Save the code, data,
claim-specific reasoning and limitations as evidence. Challenge both the signed
error and generalization to other smooth functions. Do not manufacture an error
or agreement. Use submit_review for your own assessment of all questions, with
the current version. Retain every prior objection ID/disposition and review phase
in your handoff. When linking frozen evidence, include its local Markdown
dependencies explicitly, as required by packet freezing.

Both roles: have your actual numerical job write NUMERICAL_CHECK.md in your own
task workspace (work/ for primary), containing its numerical observations and
reproduction instructions. Link that report and its code/data explicitly from
your proposal/review and handoff. This procedural filename helps the engineering
observer distinguish a numerical job from read-only inspection; all findings,
parameters, code and assessments are yours to supply.
Job-written Markdown can remain a private retained draft while your context is
active. Discover/read its immutable snapshot with control(documents/read_document)
and link [numerical report](document:ID), including its code/data dependencies
explicitly in the proposal/review. Handoffs must also use that document link when
the report is not yet canonical, or save the exact report with write_draft first.
Use write_draft for other scientific Markdown, job_run/job_wait for actual
computations and read-only inspection, and explicit evidence links. End ordinary
turns when appropriate; normal turn completion is not a terminal decision.
No exchange count or elapsed test time establishes scientific completion.
"""

TERMINAL_ACTIONS = {
    'propose_complete', 'propose_stop', 'submit_review',
    'finalize_complete', 'finalize_stop',
}
MARKERS = ('COMPLETE', 'COMPLETE_ACK', 'STOP', 'STOP_ACK')
FIXTURE_SECONDS = 1200  # Engineering interruption only, never a science allowance.
CLEANUP_SECONDS = 120


@unittest.skipUnless(os.environ.get('RESEARCH_PIPELINE_V0_L4_NATIVE') == '1',
                     'V0-L4 production validation opt-in disabled')
class NativeL4Tests(unittest.TestCase):
    def test_native_scientific_opposition_and_finalization(self):
        destination = os.environ.get('RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR')
        if not destination:
            self.fail('Enabled V0-L4 validation requires RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR')
        output = reserve_validation_output(destination)
        print(f'V0-L4 output: {output}', flush=True)
        receipt = {
            'validation': 'V0-L4 native public science and production terminal finalization',
            'requested_output_dir': str(Path(destination).absolute()), 'output_dir': str(output),
            'outcome': 'failed', 'phase': 'preflight', 'control_calls': [],
            'fixture_seconds': FIXTURE_SECONDS, 'cleanup_seconds': CLEANUP_SECONDS,
            'limitations': [
                'Engineering bounds interrupt/fail the test, never authorize scientific decisions.',
                'No injected science, consensus, quota, clock or rollover measurements.',
                'No additional native revision/rollover evidence unless actually observed.',
                'L5 resume/reopening, L6 integrated validation and human M5 acceptance remain separate.',
            ],
        }
        runtime = None
        project = output / 'project'
        engineering_root = Path(__file__).resolve().parents[1]
        original_markers = {p: workspace.file_digest(engineering_root / p) for p in MARKERS}

        async def exercise():
            nonlocal runtime
            jobs.atomic(output / 'receipt.json', receipt)  # Before production preflight.
            isolation.preflight()  # Inherited authorized bus only; no fallback.
            receipt['preflight'] = 'passed: inherited bus, Bubblewrap and cgroup prerequisites'
            (project / 'starting_evidence').mkdir(parents=True)
            (project / 'starting_evidence/RESEARCH_QUESTIONS.md').write_text(QUESTIONS)
            (project / 'AGENTS.md').write_text(INSTRUCTIONS)
            protected = workspace.fingerprints(project)
            receipt['protected_inputs_before'] = protected
            with workspace.acquire_project_lock(project):
                receipt['phase'] = 'initialize'
                runtime = collaboration.Coordinator.initialize(project, isolation.Config())
                original_control = runtime.control

                async def observe(ctx, action='check', path=None, parent='primary', offset=0, sha256=None):
                    watched = action in TERMINAL_ACTIONS or action in ('history', 'read_history')
                    event = None
                    if watched:
                        record = ctx['record']
                        event = {'context_id': record['context_id'], 'task_id': record['task_id'],
                                 'native_thread_id': record.get('native_thread_id'),
                                 'action': action, 'path': path, 'parent': parent, 'offset': offset,
                                 'sha256': sha256, 'monotonic': time.monotonic()}
                        if action in TERMINAL_ACTIONS and path:
                            try:
                                event['submitted_sha256'] = workspace.file_digest(
                                    workspace.safe_path(ctx['drafts'], path))
                            except (OSError, TypeError, ValueError) as exc:
                                # Even malformed requests reach the unchanged authenticated
                                # handler; observation must not replace its response.
                                event['observation_error'] = f'{type(exc).__name__}: {exc}'
                        receipt['control_calls'].append(event)
                    try:
                        result = await original_control(ctx, action, path, parent, offset, sha256)
                    except BaseException as exc:
                        if event is not None:
                            event['error'] = f'{type(exc).__name__}: {exc}'
                        raise
                    if event is not None:
                        event['response'] = deepcopy(result)
                        if action == 'read_history':
                            content = event['response'].pop('content')
                            event['response'].update(
                                characters=len(content), content_sha256=hashlib.sha256(content.encode()).hexdigest())
                    return result

                runtime.control = observe  # Observe only; never originate or delay a lifecycle request.
                receipt['phase'] = 'start'
                await runtime.start()
                receipt['admission'] = deepcopy(runtime.state['quota'])
                receipt['allocation'] = deepcopy(runtime.state['allocation'])
                self.assertEqual(runtime.state['limits'], isolation.Config().limits())
                self.assertEqual(runtime.state['quota']['native_observation']['provenance'], 'native')
                self.assertFalse(runtime.state['quota'].get('cutoff'))
                receipt['phase'] = 'native investigation'
                primary = asyncio.create_task(runtime.run_task('primary'))
                runtime.turns['primary'] = primary
                await primary  # Outer engineering bound also covers intake/start/finalization.
                self.assertIsNotNone(runtime.shutdown_task, runtime.state)
                self.assertTrue(await runtime.shutdown_task, runtime.state)
                receipt['phase'] = 'scientific terminal assertions'
                self.assert_scientific_terminal(runtime, receipt)
                self.assertEqual(workspace.fingerprints(project), protected)
                receipt['protected_inputs_after'] = workspace.fingerprints(project)

        async def checked_exercise():
            try:
                bound = asyncio.timeout(FIXTURE_SECONDS)
                try:
                    async with bound:
                        await exercise()
                except asyncio.TimeoutError as exc:
                    if not bound.expired():
                        raise  # Preserve an actual RPC timeout and its original diagnostics.
                    raise AssertionError(
                        f'Operational L4 fixture interrupted after {FIXTURE_SECONDS}s; no scientific outcome implied') from exc
            except BaseException as exc:
                receipt['investigation_error'] = f'{type(exc).__name__}: {exc}'
                raise
            finally:
                if runtime is not None:
                    receipt['last_exercise_phase'] = receipt['phase']
                    if 'investigation_error' in receipt:
                        receipt['interrupted_phase'] = receipt['phase']
                    receipt['phase'] = 'owned cleanup'
                    try:
                        receipt['cleanup_ok'] = await asyncio.wait_for(
                            runtime.block_and_cleanup('Explicit L4 engineering fixture cleanup'), CLEANUP_SECONDS)
                        receipt['cleanup'] = deepcopy(runtime.state.get('cleanup'))
                        self.assertTrue(receipt['cleanup_ok'], 'Owned cleanup/finalization unconfirmed; inspect receipt')
                        receipt['owned_groups_after_cleanup'] = []
                        for kind in ('contexts', 'jobs'):
                            for identifier, record in runtime.state[kind].items():
                                owner = record.get('service')
                                self.assertIsNotNone(owner, f'Missing ownership: {identifier}')
                                observation = {'kind': kind, 'id': identifier, 'owner': owner,
                                    'properties': await isolation.service_properties(owner['unit']),
                                    'group_empty': isolation.group_empty(owner['cgroup'])}
                                receipt['owned_groups_after_cleanup'].append(observation)
                                self.assertTrue(record.get('cleanup_ok'), record)
                                self.assertTrue(observation['group_empty'], observation)
                    finally:
                        try:
                            await asyncio.wait_for(runtime.close(), CLEANUP_SECONDS)
                        finally:
                            # Retain failed admissions, original deadlines, artifacts and uncertainty too.
                            receipt['runtime'] = deepcopy(runtime.state)
                self.assertEqual({p: workspace.file_digest(engineering_root / p) for p in MARKERS},
                                 original_markers, 'Engineering-root terminal markers changed')
                receipt['engineering_markers_preserved'] = original_markers

        try:
            asyncio.run(checked_exercise())
            receipt.update(outcome='passed', phase='finished')
        except BaseException as exc:
            receipt.update(outcome='failed', error=f'{type(exc).__name__}: {exc}')
            raise
        finally:
            jobs.atomic(output / 'receipt.json', receipt)

    def assert_scientific_terminal(self, runtime, receipt):
        state, project = runtime.state, runtime.project
        self.assertIn(state['state'], ('complete', 'scientific_stopped'), state)
        self.assertTrue(state.get('finalization_ok'), state)
        self.assertTrue(state.get('cleanup_ok'), state)
        self.assertTrue(collaboration.terminal_acknowledged(project, state), state)
        marker = state['terminal_marker']
        receipt['terminal'] = {'state': state['state'], 'marker': marker,
            'marker_sha256': workspace.file_digest(project / marker),
            'ack_sha256': workspace.file_digest(project / (marker + '_ACK')),
            'recorded_sha256': state['terminal_sha256'], 'note': state['terminal_note']}
        self.assertEqual(receipt['terminal']['marker_sha256'], state['terminal_sha256'])
        self.assertEqual(receipt['terminal']['ack_sha256'], state['terminal_sha256'])
        self.assertFalse(any((project / p).exists() for p in
                             (('STOP', 'STOP_ACK') if marker == 'COMPLETE' else ('COMPLETE', 'COMPLETE_ACK'))))
        for path in ('RESEARCH_STATUS.md', state['terminal_note']):
            self.assertTrue((project / path).is_file(), path)
        self.assertIn(state['terminal_note'], (project / 'RESEARCH_STATUS.md').read_text())

        opposition = state['opposition']
        opponent = opposition['opponent_id']
        self.assertIsNotNone(opponent)
        self.assertEqual({t['role'] for t in state['tasks'].values()}, {'primary', 'opponent'})
        self.assertEqual(len(state['tasks']), 2)
        self.assertTrue(opposition['history'])
        calls = receipt['control_calls']
        accepted = [e for e in calls if 'response' in e]
        for e in accepted:
            context = state['contexts'][e['context_id']]
            self.assertEqual(e['task_id'], context['task_id'])
            self.assertEqual(e['native_thread_id'], context['native_thread_id'])
            if e['action'] in TERMINAL_ACTIONS:
                self.assertEqual(e['task_id'], opponent if e['action'] == 'submit_review' else 'primary')
                self.assertTrue(e['submitted_sha256'])

        for proposal in opposition['history']:
            version = proposal['version']
            self.assertTrue(any(e['action'] == 'propose_' + proposal['intent'].lower()
                                and e['response'].get('proposal', {}).get('version') == version
                                and e['response']['opponent_id'] == opponent
                                and e['submitted_sha256'] == proposal['packet']['evidence'][0]['source_sha256']
                                for e in accepted))
            for key in ('packet', 'review_packet'):
                packet = proposal.get(key)
                if not packet:
                    continue
                self.assertEqual(jobs.read(project / packet['manifest']), packet['evidence'])
                self.assertEqual(hashlib.sha256(json.dumps(packet['evidence'], sort_keys=True).encode()).hexdigest(),
                                 packet['version'])
                for entry in packet['evidence']:
                    self.assertEqual(workspace.file_digest(project / entry['path']), entry['sha256'], entry)
            if proposal.get('review'):
                self.assertEqual(proposal['review']['version'], version)
                self.assertTrue(any(e['action'] == 'submit_review' and e['sha256'] == version
                                    and e['submitted_sha256'] == proposal['review_sha256'] for e in accepted))
                # Full challenge delivery is proven by actual authenticated history reads,
                # including all pages, not inferred from check/tasks summaries.
                self.assertTrue(any(e['task_id'] == 'primary' and e['action'] == 'history' for e in accepted))
                reads = [e for e in accepted if e['task_id'] == 'primary' and e['action'] == 'read_history'
                         and e['path'] == proposal['id'] and e['parent'] == 'review']
                text = proposal['review_text']
                offset = 0
                while True:
                    page = next((e['response'] for e in reads if e['offset'] == offset), None)
                    self.assertIsNotNone(page, f'Primary did not consume full challenge {proposal["id"]} at {offset}')
                    self.assertEqual(page['sha256'], hashlib.sha256(text.encode()).hexdigest())
                    self.assertEqual(page['content_sha256'],
                                     hashlib.sha256(text[offset:offset + page['characters']].encode()).hexdigest())
                    if page['next_offset'] is None:
                        self.assertEqual(offset + page['characters'], len(text))
                        break
                    offset = page['next_offset']

        current = runtime.current_proposal()
        final_action = 'finalize_complete' if marker == 'COMPLETE' else 'finalize_stop'
        finals = [e for e in accepted if e['action'] == final_action and e['sha256'] == current['version']]
        self.assertTrue(finals)
        self.assertEqual(finals[-1]['submitted_sha256'], current['final_request']['sha256'])
        review_reads = [e for e in accepted if e['action'] == 'read_history'
                        and e['task_id'] == 'primary' and e['path'] == current['id'] and e['parent'] == 'review']
        self.assertTrue(all(e['monotonic'] < finals[-1]['monotonic'] for e in review_reads))
        if marker == 'COMPLETE':
            self.assertEqual(current['review']['outcome'], 'agree_complete')
            self.assertTrue(decisions.eligible(current['review']))
            self.assertTrue(all(q['disposition'] != 'unresolved' and q['evidence'] for q in current['coverage']))
        else:
            self.assertEqual(state['stop_origin'], 'scientific')
            self.assertEqual(current['review']['outcome'], 'stop_challenged')
        self.assertFalse(state.get('operational_failure'))
        self.assertFalse(state['quota'].get('cutoff'))

        # Actual owned numerical work from each role. Code, commands, deadlines,
        # stdout/stderr and source artifacts remain in the runtime/packet records.
        for task_id in ('primary', opponent):
            report_path = state['tasks'][task_id]['workspace'] + '/NUMERICAL_CHECK.md'
            packet = current['packet' if task_id == 'primary' else 'review_packet']
            computations = [r for r in state['jobs'].values() if r['task_id'] == task_id
                            and r['state'] == 'completed' and r.get('returncode') == 0
                            and any(state['documents'][i]['path'] == report_path
                                    and any(e.get('original_path', e['source']) == report_path
                                            and e['source_sha256'] == state['documents'][i]['sha256']
                                            for e in packet['evidence'])
                                    for i in r.get('document_ids', []))]
            self.assertTrue(computations, f'No successful admitted computation for {task_id}')
            last = state['tasks'][task_id]['last_context_id']
            handoff = state['contexts'][last]['validated_handoff']
            self.assertTrue(handoff['artifacts'])
            self.assertTrue(handoff['artifact_evidence'])
        identities = set()
        receipt['native_evidence'] = []
        for identifier, record in state['contexts'].items():
            self.assertTrue(record.get('native_inventory_verified'), record)
            self.assertEqual(record['native_measurement']['status'], 'measured')
            self.assertNotIn(record['native_thread_id'], identities)
            identities.add(record['native_thread_id'])
            root = runtime.contexts[identifier]['root']
            receipt['native_evidence'].append({'context_id': identifier, 'task_id': record['task_id'],
                'native_thread_id': record['native_thread_id'],
                'native_measurement': record['native_measurement'],
                'native_tools': str(root / 'native-tools.json'), 'mcp_tools': str(root / 'mcp-tools.json'),
                'native_tools_sha256': workspace.file_digest(root / 'native-tools.json'),
                'mcp_tools_sha256': workspace.file_digest(root / 'mcp-tools.json')})
            self.assertTrue(receipt['native_evidence'][-1]['native_tools_sha256'])
            self.assertTrue(receipt['native_evidence'][-1]['mcp_tools_sha256'])


class NativeReceiptTests(unittest.TestCase):
    """Mocked engineering failure fixtures; no inference or scientific consensus."""

    def invoke(self, destination):
        with patch.dict(os.environ, {'RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR': str(destination)}):
            NativeL4Tests('test_native_scientific_opposition_and_finalization').test_native_scientific_opposition_and_finalization()

    def test_enabled_without_output_configuration_fails(self):
        with patch.dict(os.environ, {'RESEARCH_PIPELINE_V0_L4_NATIVE': '1',
                                    'RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR': ''}):
            with self.assertRaisesRegex(AssertionError, 'requires RESEARCH_PIPELINE_V0_L4_OUTPUT_DIR'):
                NativeL4Tests().test_native_scientific_opposition_and_finalization()

    def test_missing_prerequisite_retains_distinct_failed_receipts_before_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            requested = Path(temp) / 'requested'
            paths = []
            for attempt in range(2):
                logged = io.StringIO()
                with redirect_stdout(logged), patch.object(isolation, 'preflight', side_effect=
                        isolation.RuntimeUnavailable(f'engineering fixture: authorized bus absent {attempt}')), \
                        patch.object(collaboration.Coordinator, 'initialize') as initialize:
                    with self.assertRaisesRegex(isolation.RuntimeUnavailable, 'authorized bus absent'):
                        self.invoke(requested)
                    initialize.assert_not_called()
                output = Path(logged.getvalue().split('V0-L4 output: ')[1].strip())
                report = json.loads((output / 'receipt.json').read_text())
                paths.append(output)
                self.assertEqual(report['requested_output_dir'], str(requested))
                self.assertEqual(report['output_dir'], str(output))
                self.assertEqual(report['outcome'], 'failed')
                self.assertEqual(report['phase'], 'preflight')
                self.assertIn(f'authorized bus absent {attempt}', report['error'])
                self.assertFalse(report['control_calls'])
            self.assertNotEqual(*paths)
            self.assertIn('authorized bus absent 0', (paths[0] / 'receipt.json').read_text())

    def test_fixture_interruption_after_creation_always_cleans_up_and_closes(self):
        with tempfile.TemporaryDirectory() as temp:
            for cleanup_error in (False, True):
                with self.subTest(cleanup_error=cleanup_error):
                    runtime = SimpleNamespace(
                        control=AsyncMock(), start=AsyncMock(side_effect=InterruptedError('fixture interrupted')),
                        block_and_cleanup=AsyncMock(side_effect=RuntimeError('fixture cleanup failed')
                                                    if cleanup_error else None, return_value=True),
                        close=AsyncMock(), state={'contexts': {}, 'jobs': {}, 'terminal_committed': False})
                    logged = io.StringIO()
                    with redirect_stdout(logged), patch.object(isolation, 'preflight'), \
                            patch.object(collaboration.Coordinator, 'initialize', return_value=runtime):
                        with self.assertRaisesRegex((InterruptedError, RuntimeError),
                                                    'fixture interrupted|fixture cleanup failed'):
                            self.invoke(Path(temp) / 'requested')
                    runtime.block_and_cleanup.assert_awaited_once()
                    runtime.close.assert_awaited_once()
                    output = Path(logged.getvalue().split('V0-L4 output: ')[1].strip())
                    report = json.loads((output / 'receipt.json').read_text())
                    self.assertEqual(report['outcome'], 'failed')
                    self.assertFalse(report['runtime']['terminal_committed'])
                    self.assertIn('fixture interrupted', report['investigation_error'])
                    self.assertNotIn('terminal', report)
                    self.assertEqual(report['interrupted_phase'], 'start')
                    self.assertFalse(any((output / 'project' / p).exists() for p in MARKERS))

    def test_operational_bound_interrupts_instead_of_manufacturing_a_terminal_decision(self):
        async def waiting_start():
            await asyncio.Event().wait()
        with tempfile.TemporaryDirectory() as temp:
            runtime = SimpleNamespace(control=AsyncMock(), start=waiting_start,
                block_and_cleanup=AsyncMock(return_value=True), close=AsyncMock(),
                state={'contexts': {}, 'jobs': {}, 'terminal_committed': False})
            logged = io.StringIO()
            with redirect_stdout(logged), patch.object(isolation, 'preflight'), \
                    patch.object(collaboration.Coordinator, 'initialize', return_value=runtime), \
                    patch(__name__ + '.FIXTURE_SECONDS', .01):
                with self.assertRaisesRegex(AssertionError, 'Operational L4 fixture interrupted'):
                    self.invoke(Path(temp) / 'requested')
            runtime.block_and_cleanup.assert_awaited_once()
            runtime.close.assert_awaited_once()
            output = Path(logged.getvalue().split('V0-L4 output: ')[1].strip())
            report = json.loads((output / 'receipt.json').read_text())
            self.assertEqual(report['outcome'], 'failed')
            self.assertFalse(report['runtime']['terminal_committed'])
            self.assertFalse(report['control_calls'])
            self.assertNotIn('terminal', report)
