"""The controller's decisions (PROJECT.md §3–§7), driven through fake CLI sessions.

Each test plays the agents: it calls their tools and emits their events, then
checks what the controller did — sessions started or closed, notices delivered,
refusals, statuses and commits.
"""
import asyncio
import unittest

from research_pipeline.state import Options
from tests.helpers import FakeSession, remove, running, temp_project


def sent(harness, agent_id: str) -> str:
    """Everything the agent's current session was sent, as one text."""
    return '\n'.join(harness.session(agent_id).sent)


class ControllerTest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.root = temp_project()
        FakeSession.instances.clear()

    def tearDown(self):
        remove(self.root)

    async def spawn(self, harness, parent='primary', name='helper', backend='codex'):
        harness.write(f'agents/{parent}/brief-{name}.md', f'# Check {name}\n\nDo it.\n')
        reply = await harness.call(parent, 'spawn', task=f'brief-{name}.md', name=name, backend=backend)
        self.assertIn('Started subagent', reply)
        return reply.split()[2]

    def prepare_result(self, harness, agent_id):
        harness.write(f'agents/{agent_id}/RESULT.md', '# Result\n\nFound it.\n')
        harness.handoff(agent_id)
        harness.index(f'agents/{agent_id}', 'TASK.md', 'RESULT.md', 'HANDOFF.md', f'brief-x.md')

    # Starting ---------------------------------------------------------------------------

    async def test_start_prepares_project_and_primary_session(self):
        async with running(self.root) as harness:
            opening = harness.session('primary').launch.message
            self.assertIn('What is the integral of x^2', opening)
            self.assertIn('session 1 of primary', opening)
            for name in ('STATUS.md', 'REPORT.md', 'FOLDER_CONTENT.md', 'sources', 'tools', 'agents', 'reviews'):
                self.assertTrue((self.root / name).exists(), name)
            self.assertIn('project prepared', harness.controller.project.git('log', '--oneline'))
            self.assertEqual(harness.state.agents['reviewer'].status, 'resting')
            launch = harness.session('primary').launch
            self.assertIn(self.root / 'STATUS.md', launch.writable)
            self.assertNotIn(self.root / 'starting_evidence', launch.writable)
            self.assertIn('primary researcher', launch.instructions)

    async def test_stale_token_and_role_tools_are_refused(self):
        async with running(self.root) as harness:
            reply = await harness.controller._tool_request({'agent': 'primary', 'token': 'wrong', 'tool': 'agents'})
            self.assertIn('session has ended', reply)
            self.assertIn('not available', await harness.call('primary', 'submit_result'))
            child = await self.spawn(harness)
            self.assertIn('not available', await harness.call(child, 'complete'))

    # Spawning and results -------------------------------------------------------------------

    async def test_spawn_beyond_cap_is_refused_with_count(self):
        async with running(self.root, Options(max_agents=2, backends=['codex'])) as harness:
            await self.spawn(harness, name='first')
            harness.write('agents/primary/brief.md', '# Task\n')
            reply = await harness.call('primary', 'spawn', task='brief.md')
            self.assertIn('2/2 agents are already working', reply)
            self.assertIn('not allowed', await harness.call('primary', 'spawn', task='brief.md', backend='claude'))

    async def test_subagent_starts_with_its_task_and_inherits_cli(self):
        options = Options(primary='codex:model-x:high', backends=['codex', 'claude'])
        async with running(self.root, options) as harness:
            child = await self.spawn(harness, name='Convergence Check')
            self.assertEqual(child, 'convergence-check')
            agent = harness.state.agents[child]
            self.assertEqual((agent.model, agent.effort, agent.parent), ('model-x', 'high', 'primary'))
            self.assertIn('# Check Convergence Check', harness.session(child).launch.message)
            self.assertTrue((self.root / 'agents' / child / 'TASK.md').is_file())
            other = await self.spawn(harness, name='lit', backend='claude')
            self.assertIsNone(harness.state.agents[other].model)

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
            harness.write(f'agents/{child}/RESULT.md', '# Result\n')
            harness.handoff(child)
            harness.index(f'agents/{child}', 'TASK.md', 'RESULT.md', 'HANDOFF.md')
            reply = await harness.call(child, 'submit_result')
            self.assertIn('submitted', reply)
            self.assertIn(f'Subagent {child} submitted its result', sent(harness, 'primary'))
            self.assertEqual(harness.state.agents[child].status, 'submitted')
            await harness.emit(child, 'turn_ended', text='done')
            self.assertNotIn(child, harness.controller.sessions)
            reply = await harness.call('primary', 'reject', agent=child, feedback='Add an error estimate.')
            self.assertIn('continues', reply)
            opening = harness.session(child).launch.message
            self.assertIn('Add an error estimate.', opening)
            self.assertIn('Next: continue.', opening)  # its handoff
            await harness.call(child, 'submit_result')
            await harness.emit(child, 'turn_ended', text='done')
            self.assertIn('Accepted', await harness.call('primary', 'accept', agent=child))
            self.assertEqual(harness.state.agents[child].status, 'accepted')

    async def test_cancel_stops_the_whole_subtree(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            grandchild = await self.spawn(harness, parent=child, name='deeper')
            sessions = [harness.session(child), harness.session(grandchild)]
            await harness.call('primary', 'cancel', agent=child)
            self.assertEqual({harness.state.agents[a].status for a in (child, grandchild)}, {'cancelled'})
            self.assertTrue(all(session.closed for session in sessions))

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

    async def test_nudge_once_when_nothing_is_pending(self):
        async with running(self.root) as harness:
            await harness.emit('primary', 'turn_ended', text='')
            await harness.emit('primary', 'turn_ended', text='')
            self.assertEqual(sent(harness, 'primary').count('You ended your turn'), 1)

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
                                                                          backend='claude'))
            harness.quota.remaining['claude'] = (60.0, 80.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertEqual(harness.state.agents[claude].status, 'running')

    async def test_reject_while_the_cli_is_held_waits_and_parent_is_told(self):
        async with running(self.root) as harness:
            claude = await self.spawn(harness, name='lit', backend='claude')
            harness.write(f'agents/{claude}/RESULT.md', '# Result\n')
            harness.handoff(claude)
            harness.index(f'agents/{claude}', 'TASK.md', 'RESULT.md', 'HANDOFF.md')
            await harness.call(claude, 'submit_result')
            await harness.emit(claude, 'turn_ended', text='')
            harness.quota.remaining['claude'] = (10.0, 80.0)
            await harness.controller._check_quota()
            reply = await harness.call('primary', 'reject', agent=claude, feedback='Fix the extrapolation factor.')
            self.assertIn('continue with your feedback automatically', reply)
            self.assertEqual((harness.state.agents[claude].status, harness.state.agents[claude].pause_reason),
                             ('paused', 'quota'))
            harness.quota.remaining['claude'] = (60.0, 80.0)
            await harness.controller._check_quota()
            await harness.settle()
            self.assertEqual(harness.state.agents[claude].status, 'running')
            self.assertIn('Fix the extrapolation factor.', harness.session(claude).launch.message)
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

    async def test_complete_needs_reviewer_agreement(self):
        async with running(self.root) as harness:
            self.ready_report(harness)
            reply = await harness.call('primary', 'complete')
            self.assertIn('with the Reviewer (round 1)', reply)
            self.assertIn('Review round 1', harness.session('reviewer').launch.message)
            self.assertIn('still with the Reviewer', await harness.call('primary', 'complete'))
            self.ready_review(harness)
            reply = await harness.call('reviewer', 'verdict', review='reviews/1.md', agree=True)
            self.assertIn('COMPLETE', reply)
            self.assertEqual(harness.state.status, 'complete')
            self.assertIn('COMPLETE on', (self.root / 'STATUS.md').read_text())
            self.assertIn('investigation COMPLETE', harness.controller.project.git('log', '--oneline'))
            self.assertEqual(harness.controller.sessions, {})
            await asyncio.wait_for(harness.task, 2)

    async def test_disagreement_then_stop_challenge_then_final_stop(self):
        async with running(self.root) as harness:
            self.ready_report(harness)
            await harness.call('primary', 'complete')
            self.ready_review(harness)
            await harness.call('reviewer', 'verdict', review='1.md', agree=False)
            self.assertIn('disagrees with COMPLETE', sent(harness, 'primary'))
            self.assertIsNone(harness.state.proposal)
            await harness.emit('reviewer', 'turn_ended', text='')
            self.assertEqual(harness.state.agents['reviewer'].status, 'resting')
            self.assertIn('challenge a STOP first', await harness.call('primary', 'stop', reason='x', final=True))
            await harness.call('primary', 'stop', reason='The supplement is inaccessible.')
            self.assertIn('inaccessible', harness.session('reviewer').launch.message)
            self.assertEqual(harness.state.agents['reviewer'].sessions, 2)
            self.ready_review(harness, '2.md')
            await harness.call('reviewer', 'verdict', review='2.md', agree=False)
            self.assertIn('challenges your STOP', sent(harness, 'primary'))
            self.assertIn('stopped', await harness.call('primary', 'stop', reason='Confirmed.', final=True))
            self.assertEqual(harness.state.status, 'stopped')

    async def test_reopen_after_complete(self):
        async with running(self.root) as harness:
            self.ready_report(harness)
            await harness.call('primary', 'complete')
            self.ready_review(harness)
            await harness.call('reviewer', 'verdict', review='1.md', agree=True)
        (self.root / 'starting_evidence' / 'RESEARCH_QUESTIONS.md').write_text('A new question?\n')
        async with running(self.root) as harness:
            opening = harness.session('primary').launch.message
            self.assertIn('reopened after it ended (COMPLETE)', opening)
            self.assertIn('RESEARCH_QUESTIONS.md', opening)
            self.assertIn('A new question?', opening)
            self.assertEqual(harness.state.status, 'running')

    # Pause, resume and restart ---------------------------------------------------------------------

    async def test_pause_hands_off_stops_jobs_then_resume_reports_edits(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            job = (await harness.call(child, 'run_job', command='sleep 30', timeout_seconds=60)).split()[1]
            harness.controller.toggle_pause()
            await harness.settle()
            self.assertEqual(harness.state.status, 'pausing')
            self.assertIn('human paused', sent(harness, child))
            for agent in ('primary', child):
                harness.handoff(agent)
                await harness.emit(agent, 'turn_ended', text='')
            self.assertEqual(harness.state.status, 'paused')
            self.assertEqual(harness.state.jobs[job].status, 'cancelled')
            harness.write(f'agents/{child}/NOTES.md', '# Corrected by the human\n')
            harness.controller.toggle_pause()
            await harness.settle(10)
            self.assertEqual(harness.state.status, 'running')
            for agent in ('primary', child):
                self.assertIn(f'agents/{child}/NOTES.md', harness.session(agent).launch.message)
            self.assertIn('stopped by the human\'s pause', harness.session(child).launch.message)

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

    async def test_pause_completes_when_the_last_agent_submits_instead_of_handing_off(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            harness.controller.toggle_pause()
            await harness.settle()
            harness.handoff('primary')
            await harness.emit('primary', 'turn_ended', text='')
            harness.write(f'agents/{child}/RESULT.md', '# Result\n')
            harness.handoff(child)
            harness.index(f'agents/{child}', 'TASK.md', 'RESULT.md', 'HANDOFF.md')
            self.assertIn('submitted', await harness.call(child, 'submit_result'))
            self.assertEqual(harness.state.status, 'paused')

    async def test_accept_during_the_closing_turn_sticks_and_closed_sessions_lose_their_tools(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            harness.write(f'agents/{child}/RESULT.md', '# Result\n')
            harness.handoff(child)
            harness.index(f'agents/{child}', 'TASK.md', 'RESULT.md', 'HANDOFF.md')
            await harness.call(child, 'submit_result')
            self.assertIn('session is closing', await harness.call(child, 'run_job', command='true',
                                                                   timeout_seconds=5))
            await harness.call('primary', 'accept', agent=child)
            await harness.emit(child, 'turn_ended', text='')  # its last turn ends after the acceptance
            self.assertEqual(harness.state.agents[child].status, 'accepted')
            self.assertNotIn(child, harness.controller.sessions)

    async def test_reject_while_closing_replaces_the_old_session(self):
        async with running(self.root) as harness:
            child = await self.spawn(harness)
            harness.write(f'agents/{child}/RESULT.md', '# Result\n')
            harness.handoff(child)
            harness.index(f'agents/{child}', 'TASK.md', 'RESULT.md', 'HANDOFF.md')
            await harness.call(child, 'submit_result')
            old = harness.session(child)
            await harness.call('primary', 'reject', agent=child, feedback='More.')
            self.assertTrue(old.closed)
            self.assertIsNot(harness.session(child), old)

    async def test_failed_turn_restarts_from_handoff(self):
        async with running(self.root) as harness:
            await harness.emit('primary', 'turn_ended', text='', failed=True)
            agent = harness.state.agents['primary']
            self.assertEqual((agent.status, agent.pause_reason), ('paused', 'failure'))
            agent.retry_at = 0
            await harness.settle(10)
            self.assertEqual((agent.status, agent.sessions), ('running', 2))

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
            self.ready_report(harness)
            reply = await harness.call('primary', 'complete')
            self.assertIn('with the Reviewer', reply)
            self.assertIn('results.csv', reply)  # pending notices ride along with the tool's reply
            self.assertNotIn('.obsidian', reply)

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
