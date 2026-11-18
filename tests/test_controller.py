"""The controller's decisions (PROJECT.md §3–§7), driven through fake CLI sessions.

Each test plays the agents: it calls their tools and emits their events, then
checks what the controller did — sessions started or closed, notices delivered,
refusals, statuses and commits.
"""
import asyncio
import unittest

from research_pipeline.controller import Controller
from agent_toolkit import SetupError

from research_pipeline.project import ProjectError
from tests.helpers import FAKE_DRIVERS, FakeSession, launch_options, remove, running, temp_project


def sent(harness, agent_id: str) -> str:
    """Everything the agent's current session was sent, as one text."""
    return '\n'.join(harness.session(agent_id).sent)


class ControllerTest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.root = temp_project()
        FakeSession.reset()

    def tearDown(self):
        FakeSession.start_error = None
        remove(self.root)

    async def spawn(self, harness, parent='primary', name='helper', backend='codex', model='gpt-test', effort='high'):
        harness.write(f'agents/{parent}/brief-{name}.md', f'# Check {name}\n\nDo it.\n')
        reply = await harness.call(parent, 'spawn', task=f'brief-{name}.md', name=name, backend=backend, model=model,
                                   effort=effort)
        self.assertIn('Started subagent', reply)
        return reply.split()[2]

    def prepare_result(self, harness, agent_id):
        harness.write(f'agents/{agent_id}/RESULT.md', '# Result\n\nFound it.\n')
        harness.handoff(agent_id)
        harness.index(f'agents/{agent_id}', 'TASK.md', 'RESULT.md', 'HANDOFF.md', 'brief-x.md')

    def ready_report(self, harness):
        harness.write('REPORT.md', '# Report\n\nThe integral is 1/3.\n')
        harness.handoff('primary')
        harness.index('agents/primary', 'HANDOFF.md')

    def ready_review(self, harness, name='1.md'):
        harness.write(f'reviews/{name}', '# Review\n\n1. Fine.\n')
        harness.index('reviews', *sorted(p.name for p in (self.root / 'reviews').glob('*.md')
                                         if p.name != 'FOLDER_CONTENT.md'))
        harness.handoff('reviewer')
        harness.index('agents/reviewer', 'HANDOFF.md')

    async def propose_complete(self, harness):
        """The primary proposes COMPLETE and ends its turn; it waits in its session for the verdict."""
        self.ready_report(harness)
        reply = await harness.call('primary', 'complete')
        await harness.emit('primary', 'turn_ended', text='Proposed.')
        return reply

    # Starting ---------------------------------------------------------------------------

    async def test_start_prepares_project_and_primary_session(self):
        async with running(self.root) as harness:
            opening = harness.session('primary').launch.message
            self.assertIn('What is the integral of x^2', opening)
            self.assertIn('session 1 of primary', opening)
            for name in ('STATUS.md', 'REPORT.md', 'FOLDER_CONTENT.md', 'sources', 'tools', 'agents', 'reviews'):
                self.assertTrue((self.root / name).exists(), name)
            log = harness.controller.project.git('log', '--oneline')
            self.assertIn('project prepared', log)
            self.assertIn('investigation started', log)
            self.assertEqual(harness.state.agents['reviewer'].status, 'resting')
            launch = harness.session('primary').launch
            self.assertIn(self.root / 'STATUS.md', launch.writable)
            self.assertNotIn(self.root / 'starting_evidence', launch.writable)
            self.assertEqual(launch.hidden, (self.root / '.research',))
            self.assertEqual((launch.model, launch.effort), ('gpt-test', 'high'))
            self.assertIn('primary researcher', launch.instructions)

    async def test_launch_needs_explicit_cli_choices(self):
        controller = Controller(self.root, launch_options(primary='codex'), drivers=FAKE_DRIVERS,
                                read_quota=lambda backend: [])
        with self.assertRaises(ProjectError) as raised:
            await controller.run()
        self.assertIn('--primary must be BACKEND:MODEL:EFFORT', str(raised.exception))

    async def test_agents_md_reaches_every_session_as_instructions(self):
        (self.root / 'AGENTS.md').write_text('Use SI units throughout.\n')
        async with running(self.root) as harness:
            primary = harness.session('primary').launch
            self.assertIn('Use SI units throughout.', primary.instructions)
            self.assertNotIn('Use SI units', primary.message)
            child = await self.spawn(harness)
            self.assertIn('Use SI units throughout.', harness.session(child).launch.instructions)

    async def test_other_roles_tools_are_refused(self):
        async with running(self.root) as harness:
            self.assertIn('not one of your tools', await harness.call('primary', 'submit_result'))
            child = await self.spawn(harness)
            self.assertIn('not one of your tools', await harness.call(child, 'complete'))

    async def test_session_that_loads_personal_setup_waits_for_the_human(self):
        async with running(self.root) as harness:
            FakeSession.start_error = SetupError('codex loaded the human\'s own setup (skill personal-notes)')
            harness.write('agents/primary/brief.md', '# Task\n')
            reply = await harness.call('primary', 'spawn', task='brief.md', name='helper', backend='codex',
                                       model='gpt-test', effort='high')
            self.assertIn('could not start', reply)
            agent = harness.state.agents['helper']
            self.assertEqual((agent.status, agent.pause_reason, agent.retry_at), ('paused', 'failure', None))
            self.assertTrue(any('personal-notes' in text and 'Ctrl+R' in text for _, _, text in harness.lines))
            self.assertTrue(harness.controller.releasable)
            FakeSession.start_error = None  # the human removed it
            harness.controller.release()
            await harness.settle(10)
            self.assertEqual(agent.status, 'running')

    # Spawning, results and messages -------------------------------------------------------------

    async def test_spawn_beyond_cap_is_refused_with_count(self):
        async with running(self.root, launch_options(max_agents=2, backends=['codex'])) as harness:
            await self.spawn(harness, name='first')
            harness.write('agents/primary/brief.md', '# Task\n')
            reply = await harness.call('primary', 'spawn', task='brief.md', backend='codex', model='m', effort='low')
            self.assertIn('2/2 agent sessions are already open', reply)
            self.assertIn('not allowed', await harness.call('primary', 'spawn', task='brief.md', backend='claude',
                                                            model='m', effort='low'))

    async def test_spawn_needs_backend_model_and_effort(self):
        async with running(self.root) as harness:
            harness.write('agents/primary/brief.md', '# Task\n')
            self.assertIn('invalid arguments', await harness.call('primary', 'spawn', task='brief.md'))
            self.assertIn('model and an effort are required', await harness.call(
                'primary', 'spawn', task='brief.md', backend='codex', model='', effort='high'))
            self.assertIn('does not accept effort', await harness.call(  # refused before any session starts
                'primary', 'spawn', task='brief.md', backend='claude', model='opus', effort='enormous'))
            child = await self.spawn(harness, name='Convergence Check', backend='claude', model='opus', effort='max')
            self.assertEqual(child, 'convergence-check')
            agent = harness.state.agents[child]
            self.assertEqual((agent.backend, agent.model, agent.effort, agent.parent),
                             ('claude', 'opus', 'max', 'primary'))
            launch = harness.session(child).launch
            self.assertEqual((launch.model, launch.effort), ('opus', 'max'))
            self.assertIn('# Check Convergence Check', launch.message)
            self.assertTrue((self.root / 'agents' / child / 'TASK.md').is_file())

    async def test_result_requires_settled_children_and_layout(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            grandchild = await self.spawn(harness, parent=child, name='deeper')
            self.prepare_result(harness, child)
            reply = await harness.call(child, 'submit_result')
            self.assertIn(grandchild, reply)
            await harness.call(child, 'cancel', agent=grandchild)
            (self.root / 'agents' / child / 'FOLDER_CONTENT.md').unlink()
            self.assertIn('FOLDER_CONTENT.md is missing', await harness.call(child, 'submit_result'))

    async def test_result_is_reviewed_by_parent_reject_then_accept(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            session = harness.session(child)
            self.prepare_result(harness, child)
            reply = await harness.call(child, 'submit_result')
            self.assertIn('submitted', reply)
            self.assertIn(f'Subagent {child} submitted its result', sent(harness, 'primary'))
            self.assertEqual(harness.state.agents[child].status, 'submitted')
            self.assertIn('your result is with primary', await harness.call(child, 'run_job', command='true',
                                                                           timeout_seconds=5))
            await harness.emit(child, 'turn_ended', text='done')
            self.assertIs(harness.session(child), session)  # it waits in its session
            reply = await harness.call('primary', 'reject', agent=child, feedback='Add an error estimate.')
            self.assertIn('continues', reply)
            self.assertIs(harness.session(child), session)  # the feedback reaches the same session
            self.assertIn('Add an error estimate.', sent(harness, child))
            self.assertEqual(harness.state.agents[child].status, 'running')
            await harness.call(child, 'submit_result')
            await harness.emit(child, 'turn_ended', text='done')
            self.assertIn('Accepted', await harness.call('primary', 'accept', agent=child))
            self.assertEqual(harness.state.agents[child].status, 'accepted')
            self.assertTrue(session.closed)
            self.assertNotIn(child, harness.controller.sessions)

    async def test_cancel_stops_the_whole_subtree(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            grandchild = await self.spawn(harness, parent=child, name='deeper')
            sessions = [harness.session(child), harness.session(grandchild)]
            await harness.call('primary', 'cancel', agent=child)
            self.assertEqual({harness.state.agents[a].status for a in (child, grandchild)}, {'cancelled'})
            self.assertTrue(all(session.closed for session in sessions))

    async def test_messages_between_parent_and_subagents(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            other = await self.spawn(harness, name='other')
            grandchild = await self.spawn(harness, parent=child, name='deeper')
            self.assertIn('delivered', await harness.call('primary', 'message', agent=child, text='Use the 2024 data.'))
            self.assertIn('[from primary] Use the 2024 data.', sent(harness, child))
            self.assertIn('delivered', await harness.call(child, 'message', agent='primary', text='Which norm?'))
            self.assertIn(f'[from {child}] Which norm?', sent(harness, 'primary'))
            self.assertIn('delivered', await harness.call(grandchild, 'message', agent=child, text='Done soon.'))
            self.assertIn('neither your parent', await harness.call(child, 'message', agent=other, text='Hi.'))
            self.assertIn('neither your parent', await harness.call('primary', 'message', agent=grandchild,
                                                                    text='Hi.'))
            self.prepare_result(harness, other)
            await harness.call(other, 'submit_result')
            self.assertIn('has submitted its result', await harness.call('primary', 'message', agent=other,
                                                                         text='Wait.'))

    # Waiting, idle and stalled agents -------------------------------------------------------------

    async def test_waiting_parent_is_left_alone_and_a_stalled_subagent_is_reported_to_it(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            await harness.emit('primary', 'turn_ended', text='Waiting for the helper.')
            self.assertNotIn('You ended your turn', sent(harness, 'primary'))  # waiting, not idle
            await harness.emit(child, 'turn_ended', text='Thinking.')
            self.assertEqual(sent(harness, child).count('You ended your turn'), 1)
            await harness.emit(child, 'turn_ended', text='I am not sure which method to use.')
            self.assertIn(f'Subagent {child} has stopped working', sent(harness, 'primary'))
            self.assertIn('I am not sure which method to use.', sent(harness, 'primary'))
            self.assertEqual(harness.state.agents[child].status, 'running')  # it keeps its session
            await harness.call('primary', 'message', agent=child, text='Use method B.')
            self.assertIn('[from primary] Use method B.', sent(harness, child))

    async def test_nudge_names_results_awaiting_a_decision(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            self.prepare_result(harness, child)
            await harness.call(child, 'submit_result')
            await harness.emit(child, 'turn_ended', text='')
            await harness.emit('primary', 'turn_ended', text='')
            self.assertIn(f'results await your decision: {child}', sent(harness, 'primary'))

    async def test_stalled_primary_alerts_the_human_and_keeps_its_session(self):
        async with running(self.root) as harness:
            session = harness.session('primary')
            await harness.emit('primary', 'turn_ended', text='')
            await harness.emit('primary', 'turn_ended', text='Should I use the six-band model?')
            self.assertEqual(sent(harness, 'primary').count('You ended your turn'), 1)
            alerts = [text for kind, _, text in harness.lines if kind == 'alert']
            self.assertTrue(alerts and 'six-band' in alerts[-1])
            harness.controller.say('Yes, six bands.')
            await harness.settle()
            self.assertIs(harness.session('primary'), session)
            self.assertIn('[human] Yes, six bands.', sent(harness, 'primary'))

    async def test_stalled_reviewer_withdraws_the_proposal_and_wakes_the_primary(self):
        async with running(self.root) as harness:
            primary = harness.session('primary')
            await self.propose_complete(harness)
            await harness.emit('reviewer', 'turn_ended', text='')
            await harness.emit('reviewer', 'turn_ended', text='Nothing to add.')
            self.assertIsNone(harness.state.proposal)
            self.assertEqual(harness.state.agents['reviewer'].status, 'resting')
            self.assertIn('reviewer', harness.controller.sessions)  # it keeps its session for the next round
            self.assertIs(harness.session('primary'), primary)
            self.assertIn('stopped without a verdict', sent(harness, 'primary'))

    # Handoffs -------------------------------------------------------------------------------

    async def test_handoff_at_threshold_with_reminders_then_successor(self):
        async with running(self.root) as harness:
            first = harness.session('primary')
            await harness.emit('primary', 'context', tokens=50_000, window=100_000)
            self.assertNotIn('Your context is', sent(harness, 'primary'))
            await harness.emit('primary', 'context', tokens=56_000, window=100_000)
            self.assertIn('Your context is 56% full', sent(harness, 'primary'))
            await harness.emit('primary', 'context', tokens=75_000, window=100_000)
            self.assertNotIn('Reminder', sent(harness, 'primary'))
            await harness.emit('primary', 'context', tokens=81_000, window=100_000)
            self.assertIn('Reminder: your context is 81% full', sent(harness, 'primary'))
            await harness.emit('primary', 'context', tokens=104_000, window=100_000)
            self.assertEqual(sent(harness, 'primary').count('Reminder'), 1)  # next at 105%
            await harness.emit('primary', 'context', tokens=106_000, window=100_000)
            self.assertEqual(sent(harness, 'primary').count('Reminder'), 2)
            await harness.emit('primary', 'context', tokens=30_000, window=100_000)  # compacted: cycle restarts
            self.assertEqual(harness.state.agents['primary'].status, 'running')
            await harness.emit('primary', 'context', tokens=56_000, window=100_000)
            self.assertEqual(sent(harness, 'primary').count('Your context is 56% full'), 2)
            harness.handoff('primary')
            await harness.emit('primary', 'turn_ended', text='handed off')
            self.assertTrue(first.closed)
            successor = harness.session('primary')
            self.assertIsNot(successor, first)
            self.assertIn('session 2 of primary', successor.launch.message)
            self.assertIn('Next: continue.', successor.launch.message)
            self.assertIsNone(harness.state.agents['primary'].fill)  # unknown until the new session's CLI reports

    async def test_context_use_is_only_what_the_cli_reports(self):
        async with running(self.root) as harness:
            primary = harness.state.agents['primary']
            await harness.emit('primary', 'context', tokens=150_000, window=None)
            self.assertIsNone(primary.fill)  # no window reported yet: unknown, never assumed
            await harness.emit('primary', 'context', tokens=150_000, window=1_000_000)
            self.assertEqual(primary.status, 'running')
            self.assertNotIn('Your context is', sent(harness, 'primary'))
            await harness.emit('primary', 'context', tokens=560_000, window=None)  # window known in this session
            self.assertIn('Your context is 56% full', sent(harness, 'primary'))

    async def test_unmeasured_context_alerts_the_human_once_per_session(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            await harness.emit(child, 'context', tokens=1_000, window=100_000)
            await harness.emit(child, 'turn_ended', text='')  # measured: nothing to report
            await harness.emit('primary', 'turn_ended', text='')
            await harness.emit('primary', 'turn_ended', text='')
            alerts = [(agent, text) for kind, agent, text in harness.lines if kind == 'alert' and 'context use' in text]
            self.assertEqual(alerts, [('primary', alerts[0][1])])
            self.assertEqual(harness.state.agents['primary'].status, 'running')  # it continues

    async def test_handoff_asks_again_until_updated(self):
        async with running(self.root) as harness:
            first = harness.session('primary')
            await harness.emit('primary', 'context', tokens=60_000, window=100_000)
            await harness.emit('primary', 'turn_ended', text='')
            self.assertIn('HANDOFF.md has not been updated', sent(harness, 'primary'))
            self.assertIs(harness.session('primary'), first)
            harness.handoff('primary')
            await harness.emit('primary', 'turn_ended', text='')
            self.assertIsNot(harness.session('primary'), first)

    # Jobs -------------------------------------------------------------------------------------

    async def test_job_runs_survives_handoff_and_notifies_owner(self):
        async with running(self.root) as harness:
            reply = await harness.call('primary', 'run_job', command='sleep 0.3; echo computed', timeout_seconds=30)
            job = reply.split()[1]
            await harness.emit('primary', 'context', tokens=60_000, window=100_000)
            harness.handoff('primary')
            await harness.emit('primary', 'turn_ended', text='')
            for _ in range(100):
                await asyncio.sleep(0.05)
                if harness.state.jobs[job].status != 'running':
                    break
            await harness.settle()
            self.assertEqual(harness.state.jobs[job].status, 'finished')
            self.assertIn('computed', sent(harness, 'primary'))  # delivered to the successor session
            self.assertIn('finished', await harness.call('primary', 'job_status', job=job))
            self.assertIn('not one of your jobs', await harness.call(
                await self.spawn(harness), 'job_status', job=job))

    async def test_a_symlink_in_place_of_an_index_is_refused_without_stopping_the_handoff(self):
        outside = self.root.parent / f'{self.root.name}-outside.md'
        outside.write_text('untouched\n')
        self.addCleanup(outside.unlink, missing_ok=True)
        async with running(self.root) as harness:
            await harness.call('primary', 'run_job', command='true', timeout_seconds=30)
            index = self.root / 'agents' / 'primary' / 'jobs' / 'FOLDER_CONTENT.md'
            index.unlink(missing_ok=True)
            index.symlink_to(outside)  # what the agent, or its job, can do in its own folder
            await harness.emit('primary', 'context', tokens=60_000, window=100_000)
            harness.handoff('primary')
            await harness.emit('primary', 'turn_ended', text='')
            await harness.settle(10)
            self.assertEqual(harness.state.agents['primary'].sessions, 2)  # the handoff went through
            self.assertEqual(outside.read_text(), 'untouched\n')
            self.assertTrue(any('not written' in text and 'symlink' in text for unused, unused, text in harness.lines))

    async def test_job_timeout_and_cancel(self):
        async with running(self.root) as harness:
            slow = (await harness.call('primary', 'run_job', command='sleep 30', timeout_seconds=0.5)).split()[1]
            stuck = (await harness.call('primary', 'run_job', command='sleep 30', timeout_seconds=60)).split()[1]
            self.assertIn('cancelled', await harness.call('primary', 'job_cancel', job=stuck))
            for _ in range(100):
                await asyncio.sleep(0.05)
                if harness.state.jobs[slow].status != 'running':
                    break
            self.assertEqual(harness.state.jobs[slow].status, 'timeout')
            self.assertIn('positive', await harness.call('primary', 'run_job', command='true', timeout_seconds=0))

    async def test_jobs_cannot_write_the_evidence_or_use_the_controller_folder(self):
        async with running(self.root) as harness:
            reply = await harness.call('primary', 'run_job', command='echo x > ../../starting_evidence/new.txt',
                                       timeout_seconds=30)
            job = reply.split()[1]
            for _ in range(100):
                await asyncio.sleep(0.05)
                if harness.state.jobs[job].status != 'running':
                    break
            self.assertEqual(harness.state.jobs[job].status, 'failed')
            self.assertFalse((self.root / 'starting_evidence' / 'new.txt').exists())
            self.assertIn('not an existing folder', await harness.call(
                'primary', 'run_job', command='ls', timeout_seconds=5, cwd='.research'))

    # Usage quota --------------------------------------------------------------------------------

    async def test_short_window_pauses_only_that_cli_then_resumes(self):
        async with running(self.root) as harness:
            claude = await self.spawn(harness, name='lit', backend='claude')
            harness.quota.remaining['claude'] = (10.0, 80.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertEqual(harness.state.agents[claude].status, 'handing_off')
            self.assertIn('usage quota of claude', sent(harness, claude))
            self.assertEqual(harness.state.agents['primary'].status, 'running')
            harness.handoff(claude)
            await harness.emit(claude, 'turn_ended', text='')
            self.assertEqual(harness.state.agents[claude].status, 'paused')
            harness.write('agents/primary/b.md', '# Task\n')
            self.assertIn('paused by the usage quota', await harness.call('primary', 'spawn', task='b.md',
                                                                          backend='claude', model='m', effort='low'))
            session = harness.session(claude)
            harness.quota.remaining['claude'] = (60.0, 80.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertEqual(harness.state.agents[claude].status, 'running')
            self.assertIs(harness.session(claude), session)  # lifted within the idle limit: the same session
            self.assertIn('The usage quota allows work again', sent(harness, claude))

    async def test_an_idle_agent_saves_its_note_in_a_short_turn_at_a_hold(self):
        async with running(self.root) as harness:
            claude = await self.spawn(harness, name='lit', backend='claude')
            await harness.emit(claude, 'turn_ended', text='Thinking.')  # idle (it is then nudged)
            await harness.emit(claude, 'turn_ended', text='Still thinking.')  # stalled: its parent is told
            turns = len(harness.session(claude).sent)
            harness.quota.remaining['claude'] = (10.0, 80.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertEqual(len(harness.session(claude).sent), turns + 1)
            self.assertIn('usage quota of claude', harness.session(claude).sent[-1])

    async def test_shutdown_while_paused_lets_the_kept_sessions_save_their_notes(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            harness.controller.toggle_pause()
            await harness.settle()
            for agent in ('primary', child):
                await harness.emit(agent, 'turn_ended', text='')
            self.assertEqual(harness.state.status, 'paused')
            harness.controller.shutdown()
            await harness.settle()
            for agent in ('primary', child):
                self.assertIn('shutting the controller down', sent(harness, agent))
                harness.handoff(agent)
                await harness.emit(agent, 'turn_ended', text='')
            await asyncio.wait_for(harness.task, 2)
            self.assertEqual(harness.controller.sessions, {})

    async def test_reject_while_the_cli_is_held_waits_and_parent_is_told(self):
        async with running(self.root) as harness:
            claude = await self.spawn(harness, name='lit', backend='claude')
            session = harness.session(claude)
            self.prepare_result(harness, claude)
            await harness.call(claude, 'submit_result')
            await harness.emit(claude, 'turn_ended', text='')
            harness.quota.remaining['claude'] = (10.0, 80.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertIn('usage quota of claude', sent(harness, claude))  # a short turn for its note
            harness.handoff(claude)
            await harness.emit(claude, 'turn_ended', text='')
            self.assertEqual(harness.state.agents[claude].status, 'submitted')  # it still waits for its parent
            reply = await harness.call('primary', 'reject', agent=claude, feedback='Fix the extrapolation factor.')
            self.assertIn('continue with your feedback automatically', reply)
            self.assertEqual((harness.state.agents[claude].status, harness.state.agents[claude].pause_reason),
                             ('paused', 'quota'))
            self.assertNotIn('Fix the extrapolation factor.', sent(harness, claude))
            harness.quota.remaining['claude'] = (60.0, 80.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertEqual(harness.state.agents[claude].status, 'running')
            self.assertIs(harness.session(claude), session)
            self.assertIn('Fix the extrapolation factor.', sent(harness, claude))
            self.assertIn(f'Subagent {claude} has resumed', sent(harness, 'primary'))

    async def test_parent_is_told_its_subagent_pauses_for_quota(self):
        async with running(self.root) as harness:
            claude = await self.spawn(harness, name='lit', backend='claude')
            harness.quota.remaining['claude'] = (10.0, 80.0)
            await harness.controller._check_quota()
            harness.handoff(claude)
            await harness.emit(claude, 'turn_ended', text='')
            self.assertIn('not a scientific blocker', sent(harness, 'primary'))

    async def test_primary_cli_hold_pauses_everyone_and_weekly_waits_for_resume(self):
        async with running(self.root) as harness:
            claude = await self.spawn(harness, name='lit', backend='claude')
            job = (await harness.call(claude, 'run_job', command='sleep 30', timeout_seconds=60)).split()[1]
            harness.quota.remaining['codex'] = (80.0, 5.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertEqual({harness.state.agents[a].status for a in ('primary', claude)}, {'handing_off'})
            for agent in ('primary', claude):
                harness.handoff(agent)
                await harness.emit(agent, 'turn_ended', text='')
            harness.quota.remaining['codex'] = (80.0, 80.0)
            await harness.controller._check_quota()  # a weekly hold stays until the human resumes
            self.assertEqual(harness.state.agents['primary'].status, 'paused')
            self.assertTrue(harness.controller.releasable)
            harness.controller.toggle_pause()  # nothing works: the toggle is the human's resume, not a pause
            await harness.settle(10)
            self.assertEqual(harness.state.agents['primary'].status, 'running')
            self.assertEqual(harness.state.agents[claude].status, 'running')
            self.assertEqual(harness.state.jobs[job].status, 'running')  # quota pauses never stop jobs
            await harness.call(claude, 'job_cancel', job=job)

    async def test_weekly_hold_is_not_downgraded_by_a_short_reading(self):
        async with running(self.root) as harness:
            harness.quota.remaining['claude'] = (80.0, 5.0)
            await harness.controller._check_quota()
            harness.quota.remaining['claude'] = (5.0, 80.0)
            await harness.controller._check_quota()
            self.assertEqual(harness.state.holds['claude']['kind'], 'weekly')
            harness.quota.remaining['claude'] = (80.0, 80.0)
            await harness.controller._check_quota()
            self.assertIn('claude', harness.state.holds)  # only the human lifts it
            harness.controller.release()
            await harness.settle(10)
            self.assertNotIn('claude', harness.state.holds)

    async def test_unreadable_quota_holds_after_repeated_failure(self):
        async with running(self.root) as harness:
            harness.quota.fail.add('codex')
            await harness.controller._check_quota()
            self.assertNotIn('codex', harness.state.holds)
            await harness.controller._check_quota()
            self.assertEqual(harness.state.holds['codex']['kind'], 'unreadable')

    # COMPLETE and STOP ------------------------------------------------------------------------------

    async def test_complete_needs_reviewer_agreement(self):
        async with running(self.root) as harness:
            primary = harness.session('primary')
            reply = await self.propose_complete(harness)
            self.assertIn('with the Reviewer (round 1)', reply)
            self.assertEqual(harness.state.agents['primary'].status, 'running')
            self.assertIs(harness.session('primary'), primary)  # it waits in its session
            commit = harness.state.proposal['commit']
            self.assertEqual(commit, harness.controller.project.git('log', '-1', '--format=%H',
                                                                    '--grep', 'proposes COMPLETE').strip())
            self.assertIn('Review round 1', harness.session('reviewer').launch.message)
            self.assertIn(f'git show {commit}:PATH', harness.session('reviewer').launch.message)
            self.ready_review(harness)
            reply = await harness.call('reviewer', 'verdict', review='reviews/1.md', agree=True)
            self.assertIn('COMPLETE', reply)
            self.assertEqual(harness.state.status, 'complete')
            self.assertEqual(harness.state.agents['primary'].status, 'finished')
            self.assertIn('COMPLETE on', (self.root / 'STATUS.md').read_text())
            self.assertIn('investigation COMPLETE', harness.controller.project.git('log', '--oneline'))
            self.assertEqual(harness.controller.sessions, {})
            await asyncio.wait_for(harness.task, 2)

    async def test_proposal_needs_a_settled_layout(self):
        async with running(self.root) as harness:
            harness.write('REPORT.md', '# Report\n')
            harness.write('agents/primary/notes.md', '# Notes\n')
            self.assertIn('FOLDER_CONTENT.md', await harness.call('primary', 'complete'))
            self.assertIsNone(harness.state.proposal)

    async def test_primary_waits_talk_only_in_its_session_and_the_verdict_notes_later_changes(self):
        async with running(self.root) as harness:
            session = harness.session('primary')
            await self.propose_complete(harness)
            harness.controller.say('How confident are you?')
            await harness.settle()
            self.assertIs(harness.session('primary'), session)
            self.assertIn('[human] How confident are you?', sent(harness, 'primary'))
            self.assertIn(self.root / 'STATUS.md', session.launch.writable)  # its write scope never changes
            self.assertIn('may only talk', await harness.call('primary', 'run_job', command='true',
                                                              timeout_seconds=5))
            harness.write('agents/primary/brief.md', '# Task\n')
            self.assertIn('may only talk', await harness.call('primary', 'spawn', task='brief.md', backend='codex',
                                                              model='m', effort='low'))
            self.assertIn('still with the Reviewer', await harness.call('primary', 'complete'))
            self.assertEqual(harness.state.rounds, 1)
            harness.write('STATUS.md', '# Status\n\nEdited during the review.\n')
            await harness.emit('primary', 'turn_ended', text='Fairly confident.')  # waiting: no nudge
            self.assertNotIn('You ended your turn', sent(harness, 'primary'))
            self.ready_review(harness)
            await harness.call('reviewer', 'verdict', review='1.md', agree=False)
            self.assertIs(harness.session('primary'), session)  # the verdict arrives in the same session
            text = sent(harness, 'primary')
            self.assertIn('disagrees with COMPLETE', text)
            self.assertIn('changed since:\n- STATUS.md', text)
            self.assertNotIn('- reviews/1.md', text)

    async def test_disagreement_then_stop_challenge_then_final_stop(self):
        async with running(self.root) as harness:
            await self.propose_complete(harness)
            reviewer = harness.session('reviewer')
            self.ready_review(harness)
            await harness.call('reviewer', 'verdict', review='1.md', agree=False)
            self.assertIn('disagrees with COMPLETE', sent(harness, 'primary'))
            self.assertIsNone(harness.state.proposal)
            await harness.emit('reviewer', 'turn_ended', text='')
            self.assertEqual(harness.state.agents['reviewer'].status, 'resting')
            self.assertNotIn('You ended your turn', sent(harness, 'reviewer'))  # it waits, it is not idle
            self.assertIn('challenge a STOP first', await harness.call('primary', 'stop', reason='x', final=True))
            await harness.call('primary', 'stop', reason='The supplement is inaccessible.')
            self.assertIs(harness.session('reviewer'), reviewer)  # the same Reviewer session, round after round
            self.assertIn('inaccessible', sent(harness, 'reviewer'))
            self.assertEqual(harness.state.agents['reviewer'].sessions, 1)
            self.ready_review(harness, '2.md')
            await harness.call('reviewer', 'verdict', review='2.md', agree=False)
            self.assertIn('challenges your STOP', sent(harness, 'primary'))
            self.assertIn('stopped', await harness.call('primary', 'stop', reason='Confirmed.', final=True))
            self.assertEqual(harness.state.status, 'stopped')

    async def test_reopen_after_complete(self):
        async with running(self.root) as harness:
            await self.propose_complete(harness)
            self.ready_review(harness)
            await harness.call('reviewer', 'verdict', review='1.md', agree=True)
        (self.root / 'starting_evidence' / 'RESEARCH_QUESTIONS.md').write_text('A new question?\n')
        async with running(self.root) as harness:
            opening = harness.session('primary').launch.message
            self.assertIn('reopened after it ended (COMPLETE)', opening)
            self.assertIn('Changes since then:\n- starting_evidence/RESEARCH_QUESTIONS.md', opening)
            self.assertIn('A new question?', opening)
            self.assertEqual(harness.state.status, 'running')

    async def test_challenged_stop_lapses_when_the_primary_continues(self):
        async with running(self.root) as harness:
            harness.handoff('primary')
            harness.index('agents/primary', 'HANDOFF.md')
            await harness.call('primary', 'stop', reason='Blocked.')
            self.ready_review(harness)
            await harness.call('reviewer', 'verdict', review='1.md', agree=False)
            await harness.call('primary', 'run_job', command='true', timeout_seconds=5)
            self.assertIsNone(harness.state.proposal)
            self.assertIn('challenge a STOP first', await harness.call('primary', 'stop', reason='x', final=True))

    async def test_stray_top_level_entry_is_reported_not_blocking(self):
        async with running(self.root) as harness:
            harness.write('results.csv', '1,2\n')
            harness.write('.obsidian/app.json', '{}')
            reply = await self.propose_complete(harness)
            self.assertIn('with the Reviewer', reply)
            self.assertIn('results.csv', reply)  # pending notices ride along with the reply
            self.assertNotIn('.obsidian', reply)

    # Pause, shutdown and restart ---------------------------------------------------------------------

    async def test_pause_keeps_sessions_stops_jobs_and_resume_reports_changes_in_them(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            sessions = {agent: harness.session(agent) for agent in ('primary', child)}
            job = (await harness.call(child, 'run_job', command='sleep 30', timeout_seconds=60)).split()[1]
            harness.controller.toggle_pause()
            await harness.settle()
            self.assertEqual(harness.state.status, 'pausing')
            self.assertIn('human paused the investigation', sent(harness, child))
            self.assertNotIn('HANDOFF', sent(harness, child).split('human paused')[-1])  # no note is asked for
            for agent in ('primary', child):
                await harness.emit(agent, 'turn_ended', text='')
            self.assertEqual(harness.state.status, 'paused')
            self.assertEqual(harness.state.jobs[job].status, 'cancelled')
            self.assertEqual({harness.state.agents[a].status for a in sessions}, {'paused'})
            harness.controller.say('Why the second method?')  # the human's messages are answered, talk-only
            await harness.settle()
            self.assertIn('[human] Why the second method?', sent(harness, 'primary'))
            harness.write('agents/primary/brief.md', '# Task\n')
            self.assertIn('may only talk', await harness.call('primary', 'spawn', task='brief.md', backend='codex',
                                                              model='m', effort='low'))
            await harness.call(child, 'message', agent='primary', text='Found it.')  # other news waits
            self.assertNotIn('Found it.', sent(harness, 'primary'))
            await harness.emit('primary', 'turn_ended', text='Because it converges.')
            harness.write(f'agents/{child}/NOTES.md', '# Corrected by the human\n')
            harness.controller.toggle_pause()
            await harness.settle(10)
            self.assertEqual(harness.state.status, 'running')
            for agent, session in sessions.items():
                self.assertIs(harness.session(agent), session)
                self.assertIn(f'agents/{child}/NOTES.md', sent(harness, agent))
                self.assertIn('The investigation has resumed', sent(harness, agent))
            self.assertIn('Found it.', sent(harness, 'primary'))
            self.assertIn('stopped by the human\'s pause', sent(harness, child))

    async def test_shutdown_keeps_jobs_running_and_the_next_run_reattaches_them(self):
        async with running(self.root) as harness:
            job = (await harness.call('primary', 'run_job', command='sleep 30', timeout_seconds=60)).split()[1]
            harness.controller.shutdown()
            await harness.settle()
            self.assertIn('shutting the controller down', sent(harness, 'primary'))
            harness.handoff('primary')
            await harness.emit('primary', 'turn_ended', text='')
            await asyncio.wait_for(harness.task, 2)
            self.assertEqual((harness.state.status, harness.state.jobs[job].status), ('paused', 'running'))
        (self.root / 'agents' / 'primary' / 'NOTES.md').write_text('# Edited while the controller was off\n')
        async with running(self.root) as harness:
            await harness.settle(10)
            self.assertEqual(harness.state.jobs[job].status, 'running')  # reattached
            opening = harness.session('primary').launch.message
            self.assertIn('agents/primary/NOTES.md', opening)
            self.assertIn('by the human or by running jobs', opening)
            self.assertIn('cancelled', await harness.call('primary', 'job_cancel', job=job))

    async def test_human_file_change_reaches_primary_live(self):
        async with running(self.root) as harness:
            harness.write('FEEDBACK.md', 'Please also compute the error.\n')
            await asyncio.sleep(0.3)
            self.assertIn('FEEDBACK.md', sent(harness, 'primary'))
            harness.controller.say('Hello from the human.')
            await harness.settle()
            self.assertIn('[human] Hello from the human.', sent(harness, 'primary'))

    async def test_restart_after_crash_resumes_agents_from_handoffs(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            harness.handoff(child)
        async with running(self.root) as harness:  # the previous controller ended without a clean pause
            await harness.settle(10)
            self.assertEqual(harness.state.agents[child].status, 'running')
            self.assertIn('session 2 of', harness.session(child).launch.message)
            self.assertIn('Next: continue.', harness.session(child).launch.message)

    async def test_pause_completes_when_the_last_agent_submits_and_ends_its_turn(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            harness.controller.toggle_pause()
            await harness.settle()
            await harness.emit('primary', 'turn_ended', text='')
            self.prepare_result(harness, child)
            self.assertIn('submitted', await harness.call(child, 'submit_result'))
            self.assertEqual(harness.state.status, 'pausing')
            await harness.emit(child, 'turn_ended', text='')
            self.assertEqual(harness.state.status, 'paused')

    async def test_accept_closes_the_session_and_closed_sessions_lose_their_tools(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            self.prepare_result(harness, child)
            await harness.call(child, 'submit_result')
            await harness.call('primary', 'accept', agent=child)
            self.assertEqual(harness.state.agents[child].status, 'accepted')
            self.assertNotIn(child, harness.controller.sessions)
            self.assertIn('session has ended', await harness.call(child, 'agents'))

    async def test_a_session_idle_past_the_limit_saves_its_note_closes_and_its_next_input_starts_fresh(self):
        async with running(self.root, launch_options(idle_limit=0.005)) as harness:  # 0.3 s
            child = await self.spawn(harness)
            first = harness.session(child)
            self.prepare_result(harness, child)
            await harness.call(child, 'submit_result')
            await harness.emit(child, 'turn_ended', text='')
            await asyncio.sleep(0.5)
            self.assertIn('without news', sent(harness, child))  # one turn for its note
            self.assertEqual(harness.state.agents[child].status, 'submitted')
            harness.write(f'agents/{child}/HANDOFF.md', '# Handoff\n\nSubmitted; wait for the parent.\n')
            await harness.emit(child, 'turn_ended', text='')
            self.assertTrue(first.closed)
            self.assertNotIn(child, harness.controller.sessions)
            await harness.call('primary', 'reject', agent=child, feedback='More.')
            fresh = harness.session(child)
            self.assertIsNot(fresh, first)
            self.assertIn('Submitted; wait for the parent.', fresh.launch.message)
            self.assertIn('More.', fresh.launch.message)

    async def test_an_idle_session_with_its_note_saved_or_its_cli_held_closes_without_a_turn(self):
        async with running(self.root, launch_options(idle_limit=0.005)) as harness:
            claude = await self.spawn(harness, name='lit', backend='claude')
            harness.quota.remaining['claude'] = (10.0, 80.0)
            await harness.controller._check_quota()
            harness.handoff(claude)
            await harness.emit(claude, 'turn_ended', text='')  # its note, at the hold
            session = harness.session(claude)
            self.assertEqual(harness.state.agents[claude].pause_reason, 'quota')
            turns = len(session.sent)
            await asyncio.sleep(0.5)
            self.assertTrue(session.closed)
            self.assertEqual(len(session.sent), turns)  # no further turn while its CLI is held
            self.assertEqual(harness.state.agents[claude].status, 'paused')
            harness.quota.remaining['claude'] = (60.0, 80.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertIn('session 2 of', harness.session(claude).launch.message)

    async def test_a_resting_primary_is_woken_by_news_in_a_fresh_session(self):
        async with running(self.root, launch_options(idle_limit=0.005)) as harness:
            await harness.call('primary', 'run_job', command='sleep 1', timeout_seconds=30)
            await harness.emit('primary', 'turn_ended', text='Waiting for the job.')
            await asyncio.sleep(0.5)
            harness.handoff('primary')
            await harness.emit('primary', 'turn_ended', text='')
            self.assertEqual(harness.state.agents['primary'].status, 'resting')
            self.assertNotIn('primary', harness.controller.sessions)
            await asyncio.sleep(1)
            self.assertEqual(harness.state.agents['primary'].status, 'running')
            self.assertIn('A job ended', harness.session('primary').launch.message)

    async def test_failed_turn_restarts_from_handoff(self):
        async with running(self.root) as harness:
            await harness.emit('primary', 'turn_ended', text='', failed=True)
            agent = harness.state.agents['primary']
            self.assertEqual((agent.status, agent.pause_reason), ('paused', 'failure'))
            agent.retry_at = 0
            await harness.settle(10)
            self.assertEqual((agent.status, agent.sessions), ('running', 2))

    async def test_failed_session_is_retried_later(self):
        async with running(self.root) as harness:
            await harness.emit('primary', 'exited', reason='network error')
            agent = harness.state.agents['primary']
            self.assertEqual((agent.status, agent.pause_reason), ('paused', 'failure'))
            agent.retry_at = 0  # due now
            await harness.settle(10)
            self.assertEqual(agent.status, 'running')
            self.assertEqual(agent.sessions, 2)


if __name__ == '__main__':
    unittest.main()
