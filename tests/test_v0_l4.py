"""Consequential decision tests. Scientific judgments here are labelled fixtures."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from tests import use_checkout
use_checkout()
from tests.quota_fixture import sufficient
from tests.test_context_usage import params
from tests.test_review_repairs import context_fixture, make_project
from tests.test_v0_l2 import handoff
from research_pipeline import collaboration, decisions, isolation, job_server, jobs, verification, workspace


def markdown(fields, record, heading, **bodies):
    return '\n\n'.join('## ' + f + '\n' + (
        json.dumps(record) if f == heading else bodies.get(f, 'Engineering fixture reasoning; no native scientific claim.'))
        for f in fields) + '\n'


class DecisionFixture(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = collaboration.Coordinator.initialize(make_project(Path(self.tmp.name)), isolation.Config())
        self.state = self.runtime.state
        self.project = self.runtime.project
        sufficient(self.runtime)
        self.primary = context_fixture(self.runtime)
        self.primary['record']['native_thread_id'] = 'primary-native'
        self.runtime.quota_transport = 'first'
        self.runtime.draft(self.primary, 'work/NOTE.md', '# Public engineering fixture\nFinite enumeration.')
        (self.project / 'work/check.py').write_text('assert sum(range(10)) == 45\n')
        self.save_handoff(self.primary)
        self.scheduled = []
        async def parked(task_id):
            self.scheduled.append(task_id)
        self.patcher = patch.object(self.runtime, 'run_task', side_effect=parked)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    async def asyncTearDown(self):
        await self.runtime.block_and_cleanup('Engineering fixture cleanup')
        await self.runtime.close()

    def save_handoff(self, ctx, artifact=None):
        task = self.state['tasks'][ctx['record']['task_id']]
        self.runtime.draft(ctx, workspace.handoff_path(task['task_id']), handoff(task, artifact))

    async def adapter(self, ctx):
        ctx['token'] = 'fixture-' + ctx['record']['context_id']
        directory = ctx['root']/'transport'
        directory.mkdir()
        ctx['server'] = await isolation.control_server(
            lambda r, w: self.runtime.handle_rpc(ctx, r, w), directory)
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        return job_server.Adapter({'token': ctx['token'], 'socket': f'/proc/self/fd/{fd}/control.sock'})

    def coverage(self, dispositions=('answered',)):
        return [{'id': str(i), 'question': 'Fixture question ' + str(i), 'disposition': disposition,
                 'explanation': 'Deterministic eligibility fixture, not scientific acceptance.',
                 'evidence': ['work/check.py']} for i, disposition in enumerate(dispositions)]

    async def propose(self, intent='COMPLETE', dispositions=('answered',)):
        text = markdown(decisions.PROPOSAL_FIELDS, {'coverage': self.coverage(dispositions)},
                         'Decision record', **{'Evidence and reproduction':
                            '[Code](/project/work/check.py)\n[Results](/project/work/NOTE.md)'})
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md', text)
        result = await self.runtime.control(self.primary, 'propose_complete' if intent == 'COMPLETE' else 'propose_stop',
                                            'outputs/PROPOSAL.md')
        await self.runtime.turns[result['opponent_id']]
        return self.runtime.current_proposal(result['proposal']['version'])

    def opponent_context(self, identifier='opponent'):
        task_id = self.state['opposition']['opponent_id']
        ctx = context_fixture(self.runtime, identifier, task_id=task_id)
        ctx['record']['predecessor'] = self.state['tasks'][task_id].get('last_context_id')
        _, baseline, changes = self.runtime.science_intake(task_id)
        ctx['publication_baseline'] = baseline
        ctx['record']['science_changes'] = changes
        self.runtime.draft(ctx, self.state['tasks'][task_id]['workspace'] + '/NOTE.md',
                           '# Independent countercheck\nFixture enumerates the boundary case.')
        self.save_handoff(ctx)
        return ctx

    def review_value(self, proposal, agree=True):
        return {'version': proposal['version'], 'exhaustive': True,
                'coverage': [{'id': q['id'], 'adequate': agree, 'reason': 'Fixture adequacy judgment.'}
                             for q in proposal['coverage']],
                'outcome': ('agree_complete' if agree else 'needs_revision') if proposal['intent'] == 'COMPLETE' else 'stop_challenged',
                'objections': [{'id': 'boundary', 'substantive': True,
                                'disposition': 'resolved' if agree else 'open',
                                'reason': 'Boundary case independently tested in this fixture.'}]}

    async def review(self, proposal, agree=True, identifier='opponent'):
        ctx = self.opponent_context(identifier)
        path = self.state['tasks'][ctx['record']['task_id']]['workspace'] + '/REVIEW.md'
        fields = decisions.REVIEW_FIELDS + (('Stopping rationale', 'Further work') if proposal['intent'] == 'STOP' else ())
        self.runtime.draft(ctx, path, markdown(fields, self.review_value(proposal, agree), 'Review record'))
        await self.runtime.control(ctx, 'submit_review', path, sha256=proposal['version'])
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        self.assertTrue(self.state['tasks'][ctx['record']['task_id']].get('released'),
                        self.state['tasks'][ctx['record']['task_id']])
        return ctx

    async def finalize(self, proposal):
        delegated = {t: {'disposition': 'integrated', 'reason': 'Result integrated in fixture synthesis.'}
                     for t in self.state['tasks'] if t not in ('primary', self.state['opposition']['opponent_id'])}
        text = markdown(decisions.FINAL_FIELDS,
                         {'version': proposal['version'], 'delegated_work': delegated},
                         'Decision record', **{'Response to challenge':
                            'Primary rejects additional enumeration as unpromising; human measurement is required.'})
        self.runtime.draft(self.primary, 'outputs/FINAL.md', text)
        return await self.runtime.control(self.primary,
            'finalize_complete' if proposal['intent'] == 'COMPLETE' else 'finalize_stop',
            'outputs/FINAL.md', sha256=proposal['version'])


class DecisionsTests(DecisionFixture):
    async def unpublished_delegate(self, canonical=None):
        task = self.runtime.add_task('task-' + 'a'*32, 'An independent delegated check', 'primary')
        path = task['workspace'] + '/NOTE.md'
        if canonical is not None:
            (self.project/path).write_text(canonical)
        ctx = context_fixture(self.runtime, 'delegate', task_id=task['task_id'])
        self.runtime.draft(ctx, path, '# Private unpublished delegate evidence\nA retained counterexample.')
        self.save_handoff(ctx)
        await self.runtime.control(ctx, 'finish_task', path)
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        self.assertTrue(task['released'])
        self.assertTrue(ctx['record']['publication_pending'])
        document = next(self.state['documents'][i] for i in ctx['record']['document_ids']
                        if self.state['documents'][i]['path'] == path)
        return ctx, path, document

    async def test_review_ordinary_links_cannot_read_unpublished_sibling_evidence(self):
        delegate, source, document = await self.unpublished_delegate()
        self.assertFalse((self.project/source).exists())
        private = self.runtime.documents.raw('primary', document['document_id'])
        proposal = await self.propose()
        ctx = self.opponent_context()
        opponent_id = ctx['record']['task_id']
        adapter = await self.adapter(ctx)
        review_path = self.state['tasks'][opponent_id]['workspace'] + '/REVIEW.md'
        for target in ('document:' + document['document_id'], '/project/' + source):
            self.runtime.draft(ctx, review_path, markdown(decisions.REVIEW_FIELDS,
                self.review_value(proposal), 'Review record', **{'Evidence': '[Sibling](' + target + ')'}))
            with self.assertRaises(jobs.JobError):
                await adapter.call('control', action='submit_review', path=review_path,
                                   sha256=proposal['version'])
            self.assertNotIn('review', proposal)
            destination = self.project/self.state['tasks'][opponent_id]['workspace']/'inputs/reviews'/proposal['id']
            self.assertFalse(destination.exists())
            with self.assertRaises(jobs.JobError):
                self.runtime.documents.raw(opponent_id, document['document_id'])
        # A legitimate review can continue after the refused sources.
        self.runtime.draft(ctx, review_path, markdown(decisions.REVIEW_FIELDS,
            self.review_value(proposal, agree=False), 'Review record'))
        await adapter.call('control', action='submit_review', path=review_path, sha256=proposal['version'])
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        # Only the primary's explicit freeze shares the delegate's exact bytes.
        revised = await self.propose_document(document['document_id'])
        entry = next(e for e in revised['packet']['evidence'] if e['source'].startswith('document:'))
        successor = self.opponent_context('opponent-shared')
        self.assertEqual(successor['record']['task_id'], opponent_id)
        self.runtime.draft(successor, review_path, markdown(decisions.REVIEW_FIELDS,
            self.review_value(revised), 'Review record',
            **{'Evidence': '[Supplied frozen evidence](/project/' + entry['path'] + ')'}))
        await self.runtime.control(successor, 'submit_review', review_path, sha256=revised['version'])
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        copied = next(e for e in revised['review_packet']['evidence'] if e['source'] == entry['path'])
        self.assertEqual((self.project/copied['path']).read_bytes(), private)
        self.assertFalse((self.project/source).exists())
        self.assertEqual((delegate['drafts']/source).read_bytes(), private)
        with self.assertRaises(jobs.JobError):
            self.runtime.documents.raw(opponent_id, document['document_id'])
        await self.finalize(revised)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))

    async def test_review_shared_canonical_source_does_not_select_foreign_retained_draft(self):
        canonical = '# Published shared evidence\nThe earlier finite-domain account.'
        delegate, source, document = await self.unpublished_delegate(canonical)
        proposal = await self.propose()
        ctx = self.opponent_context()
        review_path = self.state['tasks'][ctx['record']['task_id']]['workspace'] + '/REVIEW.md'
        self.runtime.draft(ctx, review_path, markdown(decisions.REVIEW_FIELDS,
            self.review_value(proposal), 'Review record',
            **{'Evidence': '[Shared canonical evidence](/project/' + source + ')'}))
        await self.runtime.control(ctx, 'submit_review', review_path, sha256=proposal['version'])
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        entry = next(e for e in proposal['review_packet']['evidence'] if e['source'] == source)
        self.assertEqual((self.project/entry['path']).read_text(), canonical)
        self.assertEqual(proposal['review_observations'][source]['drafts'], {})
        self.assertEqual(proposal['review_observations'][source]['effective'],
                         hashlib.sha256(canonical.encode()).hexdigest())
        with self.assertRaises(jobs.JobError):
            self.runtime.documents.raw(ctx['record']['task_id'], document['document_id'])
        # A later private batch is irrelevant to the reviewed canonical version.
        (delegate['drafts']/source).write_text('# Different unpublished private evidence')
        self.runtime.validate_reviewed_versions(proposal)
        (self.project/source).write_text('# Human correction to shared evidence')
        with self.assertRaisesRegex(jobs.JobError, 'reassessment'):
            await self.finalize(proposal)
        self.assertFalse((self.project/'COMPLETE_ACK').exists())

    async def assert_published_review_correction(self, countercheck=False):
        proposal = await self.propose()
        ctx = await self.review(proposal)
        await self.roll_primary()
        path = (self.state['tasks'][ctx['record']['task_id']]['workspace'] + '/NOTE.md'
                if countercheck else proposal['review_path'])
        self.assertFalse(ctx['record']['publication_pending'])
        self.assertEqual(ctx['record']['publication_conflicts'], [])
        self.assertEqual((self.project/path).read_bytes(), (ctx['drafts']/path).read_bytes())
        correction = '# Human correction\nThe boundary counterexample invalidates agreement.'
        (self.project/path).write_text(correction)
        with self.assertRaisesRegex(jobs.JobError, 'reassessment'):
            await self.finalize(proposal)
        self.assertTrue(proposal.get('invalidated'))
        self.assertEqual((self.project/path).read_text(), correction)
        self.assertFalse((self.project/'COMPLETE_ACK').exists())

    async def test_published_review_human_correction_invalidates_agreement(self):
        await self.assert_published_review_correction()

    async def test_published_countercheck_human_correction_invalidates_agreement(self):
        await self.assert_published_review_correction(countercheck=True)

    async def test_identical_review_publication_preserves_agreement(self):
        proposal = await self.propose()
        ctx = await self.review(proposal)
        await self.roll_primary()
        self.assertEqual(workspace.file_digest(self.project/proposal['review_path']),
                         proposal['review_sha256'])
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))
        self.assertTrue(ctx['record']['cleanup_ok'])

    async def test_opponent_reassesses_published_corrections_in_a_new_review(self):
        proposal = await self.propose()
        previous = await self.review(proposal)
        await self.roll_primary()
        note = self.state['tasks'][previous['record']['task_id']]['workspace'] + '/NOTE.md'
        for path in (note, proposal['review_path']):
            (self.project/path).write_text('# Human correction\nCountercheck missed a boundary condition.')
        with self.assertRaisesRegex(jobs.JobError, 'reassessment'):
            await self.finalize(proposal)
        revised = await self.propose()
        ctx = self.opponent_context('opponent-reassessed')
        path = proposal['review_path']
        self.runtime.draft(ctx, note, '# Revised independent check\nExplicit boundary calculation (engineering fixture).')
        self.runtime.draft(ctx, path, markdown(decisions.REVIEW_FIELDS, self.review_value(revised), 'Review record'))
        for source in (note, path):
            await self.runtime.control(ctx, 'incorporate_edit', source,
                                       sha256=workspace.file_digest(self.project/source))
        await self.runtime.control(ctx, 'submit_review', path, sha256=revised['version'])
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        self.assertEqual(ctx['record']['task_id'], previous['record']['task_id'])
        await self.finalize(revised)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))

    async def test_review_reproduction_data_is_frozen_and_version_bound(self):
        proposal = await self.propose()
        ctx = self.opponent_context()
        root = self.state['tasks'][ctx['record']['task_id']]['workspace']
        data = root + '/countercheck.json'
        original = '{"engineering_fixture": true, "boundary": 0}\n'
        (self.project/data).write_text(original)
        review_path = root + '/REVIEW.md'
        self.runtime.draft(ctx, review_path, markdown(
            decisions.REVIEW_FIELDS, self.review_value(proposal), 'Review record',
            **{'Evidence': '[Reproduction data](/project/' + data + ')'}))
        await self.runtime.control(ctx, 'submit_review', review_path, sha256=proposal['version'])
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        entry = next(e for e in proposal['review_packet']['evidence'] if e['source'] == data)
        self.assertEqual((self.project/entry['path']).read_text(), original)
        (self.project/data).write_text('{"engineering_fixture": true, "boundary": 1}\n')
        with self.assertRaisesRegex(jobs.JobError, 'reassessment'):
            await self.finalize(proposal)
        self.assertFalse((self.project/'COMPLETE_ACK').exists())

    async def test_published_review_correction_during_final_cleanup_prevents_acknowledgement(self):
        proposal = await self.propose()
        await self.review(proposal)
        await self.roll_primary()
        close = self.runtime.close_context
        async def correct_after_closure(identifier, **kwargs):
            result = await close(identifier, **kwargs)
            if identifier == self.primary['record']['context_id']:
                (self.project/proposal['review_path']).write_text(
                    '# Human correction\nAgreement no longer holds.')
            return result
        with patch.object(self.runtime, 'close_context', side_effect=correct_after_closure):
            await self.finalize(proposal)
            self.assertFalse(await self.runtime.shutdown_task)
        self.assertTrue(self.state['cleanup_ok'])
        self.assertEqual(self.state['state'], 'reassessment_required')
        self.assertFalse((self.project/'COMPLETE_ACK').exists())

    async def test_decision_history_reads_preserve_secondary_scope(self):
        task = self.runtime.add_task('task-' + 'a'*32, 'An unrelated check', 'primary')
        ctx = context_fixture(self.runtime, 'delegate', task_id=task['task_id'])
        self.runtime.draft(ctx, task['workspace'] + '/NOTE.md', '# Unrelated evidence')
        self.save_handoff(ctx)
        adapter = await self.adapter(ctx)
        for action in ('history', 'read_history'):
            with self.assertRaisesRegex(jobs.JobError, 'scoped'):
                await adapter.call('control', action=action, path='unknown', parent='review')

    async def test_large_repeated_reviews_remain_accessible_through_adapter(self):
        adapter = await self.adapter(self.primary)
        originals = {}
        for cycle in range(5):
            text = markdown(decisions.PROPOSAL_FIELDS, {'coverage': self.coverage()},
                            'Decision record', **{'Evidence and reproduction':
                                '[Code](/project/work/check.py)'})
            text = text.replace('## Results\n', '## Results\n' + 'P' * (256 * 1024 - len(text.encode())))
            await adapter.call('write_draft', path='outputs/PROPOSAL.md', content=text)
            result = await adapter.call('control', action='propose_complete', path='outputs/PROPOSAL.md')
            await self.runtime.turns[result['opponent_id']]
            proposal = self.runtime.current_proposal(result['proposal']['version'])
            ctx = self.opponent_context('opponent-' + str(cycle))
            ctx['record']['input_changes'] = []
            intake = self.runtime.successor_documents(ctx['record']['task_id'])
            opponent_adapter = await self.adapter(ctx)
            path = self.state['tasks'][ctx['record']['task_id']]['workspace'] + '/REVIEW.md'
            review = markdown(decisions.REVIEW_FIELDS, self.review_value(proposal, agree=cycle == 4),
                              'Review record')
            review = review.replace('## Independent approach\n',
                '## Independent approach\n' + 'R' * (256 * 1024 - len(review.encode())))
            await opponent_adapter.call('write_draft', path=path, content=review)
            await opponent_adapter.call('control', action='submit_review', path=path, sha256=proposal['version'])
            await asyncio.gather(*self.runtime.lifecycle_tasks)
            originals[proposal['id']] = {'proposal': text, 'review': review}
            for action in ('check', 'tasks'):
                status = await adapter.call('control', action=action)
                self.assertLess(len(json.dumps(status).encode()), 1024 * 1024)
                self.assertEqual(status['opposition']['current'], proposal['id'])
        self.assertLess(len(json.dumps(status).encode()), 128 * 1024)
        self.assertLess(len(json.dumps(intake).encode()), 128 * 1024)
        self.assertNotIn('proposal_text', json.dumps(status))
        self.assertNotIn('review_text', json.dumps(intake))
        task_page = await adapter.call('control', action='tasks', offset=1)
        self.assertEqual(task_page['tasks_total'], 2)
        self.assertEqual(set(task_page['tasks']), {result['opponent_id']})
        entries, offset = [], 0
        while offset is not None:
            page = await adapter.call('control', action='history', offset=offset)
            entries.extend(page['history'])
            offset = page['next_offset']
        self.assertEqual({p['id'] for p in entries}, set(originals))
        self.assertGreater(len(originals), decisions.HISTORY_PAGE_SIZE)
        for entry in entries:
            for part in ('proposal', 'review'):
                chunks, offset = [], 0
                while offset is not None:
                    page = await adapter.call('control', action='read_history', path=entry['id'],
                                              parent=part, offset=offset)
                    self.assertLess(len(json.dumps(page).encode()), 128 * 1024)
                    chunks.append(page['content'])
                    offset = page['next_offset']
                self.assertEqual(''.join(chunks), originals[entry['id']][part])
        for arguments in ({'action': 'history', 'offset': -1},
                          {'action': 'read_history', 'path': proposal['id'], 'parent': 'missing'},
                          {'action': 'read_history', 'path': 'missing', 'parent': 'review'}):
            with self.assertRaises(jobs.JobError):
                await adapter.call('control', **arguments)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))

    async def roll_primary(self, before_attach=None, identifier='successor'):
        """Real rollover/publication, with a labelled checkpoint/backend double."""
        previous = self.primary
        context_id = previous['record']['context_id']
        self.runtime.observe_context(context_id,
            params(thread=previous['record']['native_thread_id']),
            provenance='injected-L4-review-repair-rollover')
        async def attach(task_id):
            if before_attach:
                before_attach()
            current, baseline, changes = self.runtime.science_intake(task_id)
            successor = context_fixture(self.runtime, identifier, task_id=task_id)
            successor.update(baseline=current, publication_baseline=baseline)
            successor['record'].update(
                native_thread_id=identifier + '-native', predecessor=context_id,
                input_changes=sorted(changes), science_changes=changes)
            self.state['tasks'][task_id]['operational_state'] = 'working'
            self.runtime.quota_transport = identifier
            self.state['quota']['transport_unavailable'] = False
            sufficient(self.runtime)
            self.primary = successor
            return identifier
        with patch.object(self.runtime, 'native_turn', AsyncMock()), \
             patch.object(self.runtime, 'attach', side_effect=attach):
            await self.runtime.rollover('primary', context_id)
        self.save_handoff(self.primary)
        return previous

    async def test_rollover_retained_published_draft_cannot_hide_human_edit_before_attach(self):
        await self.assert_retained_draft_preserves_human_edit(before_attach=True)

    async def test_rollover_retained_published_draft_cannot_hide_human_edit_after_attach(self):
        await self.assert_retained_draft_preserves_human_edit(before_attach=False)

    async def assert_retained_draft_preserves_human_edit(self, before_attach):
        note = self.project/'work/NOTE.md'
        human = '# Human correction\nThe boundary changes the conclusion.'
        previous = await self.roll_primary(
            before_attach=lambda: note.write_text(human) if before_attach else None)
        if not before_attach:
            note.write_text(human)
        self.assertEqual(previous['record']['publication_conflicts'], [])
        self.assertFalse((self.primary['drafts']/'work/NOTE.md').exists())
        self.assertNotEqual(self.runtime.effective_bytes('work/NOTE.md'), note.read_bytes())
        with self.assertRaisesRegex(jobs.JobError, 'Incorporate current human edit'):
            await self.propose()
        self.assertEqual(self.state['opposition']['history'], [])
        self.assertEqual(note.read_text(), human)
        self.assertFalse((self.project/'COMPLETE_ACK').exists())

    async def test_published_predecessor_without_human_edit_can_be_reviewed_after_rollover(self):
        await self.roll_primary()
        proposal = await self.propose()
        self.assertEqual(proposal['observations']['work/NOTE.md']['effective'],
                         workspace.file_digest(self.project/'work/NOTE.md'))
        await self.review(proposal)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))

    async def propose_document(self, document_id):
        text = markdown(decisions.PROPOSAL_FIELDS, {
            'coverage': [{**self.coverage()[0], 'evidence': ['document:' + document_id]}]},
            'Decision record', **{'Evidence and reproduction': '[Earlier note](document:' + document_id + ')'})
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md', text)
        result = await self.runtime.control(self.primary, 'propose_complete', 'outputs/PROPOSAL.md')
        await self.runtime.turns[result['opponent_id']]
        return self.runtime.current_proposal(result['proposal']['version'])

    def note_document(self, ctx):
        return next(self.state['documents'][i] for i in ctx['record']['document_ids']
                    if self.state['documents'][i]['path'] == 'work/NOTE.md')

    async def test_immutable_document_requires_human_edit_incorporation_before_successor_attach(self):
        await self.assert_document_correction_incorporation(before_attach=True)

    async def test_immutable_document_requires_human_edit_incorporation_after_successor_attach(self):
        await self.assert_document_correction_incorporation(before_attach=False)

    async def assert_document_correction_incorporation(self, before_attach):
        note = self.project/'work/NOTE.md'
        human = '# Human correction\nThe boundary invalidates the original conclusion.'
        previous = await self.roll_primary(
            before_attach=(lambda: note.write_text(human)) if before_attach else None)
        document = self.note_document(previous)
        document_id = document['document_id']
        snapshot = self.runtime.documents.raw('primary', document_id)
        if not before_attach:
            note.write_text(human)
        self.assertEqual(previous['record']['publication_conflicts'], [])
        self.assertFalse((self.primary['drafts']/'work/NOTE.md').exists())
        with self.assertRaisesRegex(jobs.JobError, 'Incorporate current human edit'):
            await self.propose_document(document_id)
        self.assertFalse(self.state['opposition']['history'])
        self.assertEqual(note.read_text(), human)
        self.assertEqual(self.runtime.documents.raw('primary', document_id), snapshot)
        self.assertFalse((self.project/'COMPLETE_ACK').exists())

        correction = human + '\n\n## Revised finding\nUse only the independently checked finite domain.'
        self.runtime.draft(self.primary, 'work/NOTE.md', correction)
        with self.assertRaisesRegex(jobs.JobError, 'Incorporate current human edit'):
            await self.propose_document(document_id)
        await self.runtime.control(self.primary, 'incorporate_edit', 'work/NOTE.md',
                                   sha256=workspace.file_digest(note))
        self.runtime.draft(self.primary, 'work/NOTE.md', correction + '\nUnacknowledged revision.')
        with self.assertRaisesRegex(jobs.JobError, 'Incorporate current human edit'):
            await self.propose_document(document_id)
        await self.runtime.control(self.primary, 'incorporate_edit', 'work/NOTE.md',
                                   sha256=workspace.file_digest(note))
        corrected_bytes = self.runtime.effective_bytes('work/NOTE.md')
        proposal = await self.propose_document(document_id)
        frozen = {entry['source']: entry for entry in proposal['packet']['evidence']}
        self.assertEqual((self.project/frozen['document:' + document_id]['path']).read_bytes(), snapshot)
        self.assertEqual((self.project/frozen['work/NOTE.md']['path']).read_bytes(), corrected_bytes)
        self.assertEqual(self.runtime.documents.raw('primary', document_id), snapshot)
        await self.review(proposal)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))
        self.assertEqual((self.project/'COMPLETE').read_bytes(), (self.project/'COMPLETE_ACK').read_bytes())
        self.assertEqual(self.runtime.documents.raw('primary', document_id), snapshot)

    async def test_unchanged_document_remains_reviewable_after_publication_and_rollover(self):
        previous = await self.roll_primary()
        document = self.note_document(previous)
        proposal = await self.propose_document(document['document_id'])
        self.assertIn('document:' + document['document_id'],
                      {entry['source'] for entry in proposal['packet']['evidence']})

    async def test_document_with_missing_retained_draft_cannot_hide_canonical_correction(self):
        previous = await self.roll_primary()
        document = self.note_document(previous)
        (previous['drafts']/'work/NOTE.md').unlink()
        (self.project/'work/NOTE.md').write_text('# Human correction after publication')
        snapshot = self.runtime.documents.raw('primary', document['document_id'])
        with self.assertRaisesRegex(jobs.JobError, 'Incorporate current human edit'):
            await self.propose_document(document['document_id'])
        self.assertFalse(self.state['opposition']['history'])
        self.assertEqual(self.runtime.documents.raw('primary', document['document_id']), snapshot)

    async def test_selected_job_draft_cannot_use_fresh_job_baseline_to_hide_human_edit(self):
        path = 'work/JOB.md'
        (self.project/path).write_text('# Human correction after context attachment')
        drafts = self.project/'.research_pipeline/jobs/fixture/drafts'
        (drafts/'work').mkdir(parents=True)
        (drafts/path).write_text('# Job draft that omits the human correction')
        self.state['jobs']['fixture'] = {
            'job_id': 'fixture', 'task_id': 'primary', 'origin_context_id': 'first',
            'state': 'completed', 'cleanup_ok': True, 'drafts': str(drafts),
            'science_baseline': workspace.science_fingerprints(self.project)}
        text = markdown(decisions.PROPOSAL_FIELDS, {'coverage': self.coverage()}, 'Decision record',
                        **{'Evidence and reproduction': '[Code](/project/work/check.py)\n[Job](/project/work/JOB.md)'})
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md', text)
        with self.assertRaisesRegex(jobs.JobError, 'Incorporate current human edit.*JOB.md'):
            await self.runtime.control(self.primary, 'propose_complete', 'outputs/PROPOSAL.md')
        self.assertFalse(self.state['opposition']['history'])

    async def test_complete_after_incorporating_predecessor_publication_conflict(self):
        await self.assert_finalization_after_conflict_incorporation('COMPLETE')

    async def test_complete_after_incorporating_predecessor_job_publication_conflict(self):
        await self.assert_finalization_after_conflict_incorporation('COMPLETE', job_conflict=True)

    async def test_scientific_stop_after_incorporating_predecessor_publication_conflict(self):
        await self.assert_finalization_after_conflict_incorporation('STOP')

    async def assert_finalization_after_conflict_incorporation(self, intent, job_conflict=False):
        note = self.project/'work/NOTE.md'
        human = '# Human domain restriction\nOnly the finite checked domain is supported.'
        job = None
        if job_conflict:
            original = self.primary['drafts']/'work/NOTE.md'
            drafts = self.project/'.research_pipeline/jobs/fixture/drafts'
            (drafts/'work').mkdir(parents=True)
            (drafts/'work/NOTE.md').write_bytes(original.read_bytes())
            original.unlink()
            job = {'job_id': 'fixture', 'task_id': 'primary', 'origin_context_id': 'first',
                   'state': 'completed', 'cleanup_ok': True, 'drafts': str(drafts),
                   'science_baseline': dict(self.primary['baseline'])}
            self.state['jobs']['fixture'] = job
            self.runtime.jobs.publish(job)
        note.write_text(human)
        previous = await self.roll_primary()
        conflict = (job if job_conflict else previous['record'])['publication_conflicts'][0]
        self.assertEqual(conflict['path'], 'work/NOTE.md')
        self.assertNotIn('resolution', conflict)
        correction = human + '\n\n# Revised analysis\nBoundary countercheck incorporated.'
        self.runtime.draft(self.primary, 'work/NOTE.md', correction)
        human_hash = workspace.file_digest(note)
        await self.runtime.control(self.primary, 'incorporate_edit', 'work/NOTE.md', sha256=human_hash)
        proposal = await self.propose(intent)
        await self.review(proposal)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))
        self.assertEqual(note.read_text(), correction)
        self.assertEqual(conflict['resolution'], {
            'source_id': 'successor', 'sha256': workspace.file_digest(note), 'human_sha256': human_hash})
        # Conflict proposals and the exact human version remain available.
        self.assertTrue((self.project/conflict['proposal']).exists())
        self.assertTrue(any(human in path.read_text()
                            for path in (self.project/'handoffs/preserved').glob('*.md')))
        self.assertEqual((self.project/intent).read_bytes(), (self.project/(intent+'_ACK')).read_bytes())

    async def test_unresolved_predecessor_conflict_still_prevents_finalization(self):
        path = 'work/UNFINISHED.md'
        self.runtime.draft(self.primary, path, '# Original unresolved finding')
        (self.project/path).write_text('# Human correction requiring reconciliation')
        previous = await self.roll_primary()
        proposal = await self.propose()
        await self.review(proposal)
        await self.finalize(proposal)
        self.assertFalse(await self.runtime.shutdown_task)
        self.assertIn('Unresolved publication', self.state['terminal_error'])
        self.assertNotIn('resolution', previous['record']['publication_conflicts'][0])
        self.assertFalse((self.project/'COMPLETE_ACK').exists())

    async def test_delegation_wins_admission_lock_before_opponent_reactivation(self):
        proposal = await self.propose()
        await self.review(proposal, agree=False)
        opponent_id = self.state['opposition']['opponent_id']
        inputs = self.project/self.state['tasks'][opponent_id]['workspace']/'inputs'
        retained_packets = set(inputs.iterdir())
        self.runtime.draft(self.primary, 'work/ASSIGNMENT.md',
            markdown(verification.ASSIGNMENT_FIELDS, {}, 'unused',
                     **{'Artifacts': '[Code](/project/work/check.py)'}))
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md', proposal['proposal_text'])
        async with self.runtime.jobs.lock:
            delegation = asyncio.create_task(self.runtime.control(
                self.primary, 'delegate', 'work/ASSIGNMENT.md'))
            await asyncio.sleep(0)
            reactivation = asyncio.create_task(self.runtime.control(
                self.primary, 'propose_complete', 'outputs/PROPOSAL.md'))
            await asyncio.sleep(0)
            self.assertFalse(delegation.done())
            self.assertFalse(reactivation.done())
        delegate = await delegation
        with self.assertRaisesRegex(jobs.JobError, 'No slot.*' + delegate['task_id']):
            await reactivation
        self.assertTrue(self.state['tasks'][opponent_id]['released'])
        self.assertEqual(self.state['opposition']['current'], proposal['id'])
        self.assertEqual(len(self.state['opposition']['history']), 1)
        self.assertEqual(set(inputs.iterdir()), retained_packets)
        self.assertEqual(sum(not task.get('released') for task in self.state['tasks'].values()), 2)

    async def test_multiple_revisions_same_opponent_substantive_objection_blocks_complete(self):
        ids = []
        for i in range(4):
            proposal = await self.propose()
            ids.append(self.state['opposition']['opponent_id'])
            await self.review(proposal, agree=i == 3, identifier='opponent-' + str(i))
            if i < 3:
                with self.assertRaisesRegex(jobs.JobError, 'opposition prevents'):
                    await self.finalize(proposal)
                self.runtime.draft(self.primary, 'work/NOTE.md', f'# Supported revision {i}\nReassess boundary.')
                self.assertFalse((self.project / 'COMPLETE_ACK').exists())
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(len(self.state['opposition']['history']), 4)
        result = await self.finalize(proposal)
        self.assertEqual(result['status'], 'finalization_pending')
        self.assertTrue(self.state['admission_block'])
        self.assertTrue(await self.runtime.shutdown_task, self.state)
        self.assertEqual(self.state['state'], 'complete')
        self.assertEqual((self.project/'COMPLETE').read_bytes(), (self.project/'COMPLETE_ACK').read_bytes())
        self.assertTrue(self.state['terminal_committed'])
        self.assertFalse((Path.cwd() / 'COMPLETE').exists())
        self.assertTrue(all(r['cleanup_ok'] for r in self.state['contexts'].values()))
        before = (self.project/'COMPLETE_ACK').read_bytes()
        await self.runtime.block_and_cleanup('Later pause')
        self.assertEqual(self.state['state'], 'complete')
        self.assertEqual((self.project/'COMPLETE_ACK').read_bytes(), before)

    async def test_negative_inconclusive_and_supported_unanswerable_coverage_qualify(self):
        proposal = await self.propose(dispositions=('answered', 'negative', 'inconclusive', 'unanswerable'))
        await self.review(proposal)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state)

    async def test_inadequate_or_omitted_opponent_coverage_cannot_claim_agreement(self):
        proposal = await self.propose()
        for mutation in ('omitted', 'inadequate', 'not_exhaustive', 'open_flaw'):
            value = self.review_value(proposal)
            if mutation == 'omitted': value['coverage'] = []
            if mutation == 'inadequate': value['coverage'][0]['adequate'] = False
            if mutation == 'not_exhaustive': value['exhaustive'] = False
            if mutation == 'open_flaw': value['objections'][0]['disposition'] = 'open'
            with self.assertRaises(workspace.InputError):
                decisions.review(markdown(decisions.REVIEW_FIELDS, value, 'Review record'), proposal)

    async def test_complete_requires_supported_question_account(self):
        for coverage in ([], self.coverage(('unresolved',)), [{**self.coverage()[0], 'evidence': []}]):
            with self.assertRaises(workspace.InputError):
                decisions.proposal(markdown(decisions.PROPOSAL_FIELDS, {'coverage': coverage}, 'Decision record'), 'COMPLETE')

    async def test_only_primary_proposes_and_finalizes_only_opponent_reviews(self):
        proposal = await self.propose()
        ctx = self.opponent_context()
        for action in ('propose_complete', 'propose_stop', 'finalize_complete', 'finalize_stop', 'retire_task'):
            with self.assertRaisesRegex(jobs.JobError, 'Only primary'):
                await self.runtime.control(ctx, action, 'anything', sha256=proposal['version'])
        with self.assertRaisesRegex(jobs.JobError, 'designated'):
            await self.runtime.control(self.primary, 'submit_review', 'anything', sha256=proposal['version'])
        for action in ('complete', 'stop', 'respond', 'close'):
            with self.assertRaisesRegex(jobs.JobError, 'legacy'):
                await self.runtime.control(self.primary, action)
        self.assertFalse(self.state.get('terminal_committed'))

    async def test_scientific_stop_hears_challenge_primary_rejects_further_work(self):
        proposal = await self.propose('STOP', ('unresolved',))
        with self.assertRaisesRegex(jobs.JobError, 'delivered opponent'):
            await self.finalize(proposal)
        await self.review(proposal, agree=False)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state)
        self.assertEqual(self.state['stop_origin'], 'scientific')
        self.assertEqual(self.state['state'], 'scientific_stopped')
        text = (self.project/'STOP').read_text()
        self.assertIn('unpromising', text)
        self.assertIn('"disposition": "open"', text)
        self.assertEqual(text, (self.project/'STOP_ACK').read_text())
        self.assertFalse((self.project/'COMPLETE').exists())

    async def test_changed_questions_feedback_code_or_draft_invalidate_agreement(self):
        # Each changed input invalidates its own proposal; reassessment is explicit.
        for index, source in enumerate(('questions', 'feedback', 'code', 'draft')):
            proposal = await self.propose()
            await self.review(proposal, identifier='opponent-' + str(index))
            if source == 'questions':
                (self.project/'starting_evidence/RESEARCH_QUESTIONS.md').write_text('A changed scientific question.')
            if source == 'feedback':
                (self.project/'HUMAN_FEEDBACK.md').write_text('Consider this correction.')
            if source == 'code':
                (self.project/'work/check.py').write_text('assert False\n')
            if source == 'draft':
                self.runtime.draft(self.primary, 'work/NOTE.md', '# New unsupported central claim')
            with self.assertRaisesRegex(jobs.JobError, 'reassessment'):
                await self.finalize(proposal)
            self.assertTrue(proposal.get('invalidated'))
            self.assertFalse((self.project/'COMPLETE_ACK').exists())

    async def test_identical_publication_keeps_agreement_changed_canonical_does_not(self):
        proposal = await self.propose()
        await self.review(proposal)
        (self.project/'work/NOTE.md').write_bytes(self.runtime.effective_bytes('work/NOTE.md'))
        self.runtime.validate_reviewed_versions(proposal)
        (self.project/'work/NOTE.md').write_text('# Human corrected conclusion')
        with self.assertRaisesRegex(jobs.JobError, 'reassessment'):
            await self.finalize(proposal)
        self.assertEqual((self.project/'work/NOTE.md').read_text(), '# Human corrected conclusion')

    async def test_successor_draft_and_deferred_job_revision_invalidate(self):
        for index, kind in enumerate(('context', 'job')):
            proposal = await self.propose()
            await self.review(proposal, identifier='opponent-' + str(index))
            if kind == 'context':
                await self.runtime.close_context(self.primary['record']['context_id'])
                self.primary = context_fixture(self.runtime, 'successor')
                self.state['quota']['transport_unavailable'] = False
                self.runtime.quota_transport = 'successor'
                sufficient(self.runtime)
                self.runtime.draft(self.primary, 'work/NOTE.md', '# Successor revision')
                self.save_handoff(self.primary)
            else:
                root = self.project/'.research_pipeline/jobs/fixture/drafts'
                (root/'work').mkdir(parents=True)
                (root/'work/NOTE.md').write_text('# Deferred changed job revision')
                self.state['jobs']['fixture'] = {'job_id': 'fixture', 'task_id': 'primary',
                    'state': 'completed', 'cleanup_ok': True, 'drafts': str(root)}
            with self.assertRaisesRegex(jobs.JobError, 'reassessment'):
                self.runtime.validate_reviewed_versions(proposal)

    async def test_prior_objections_cannot_disappear_in_later_review(self):
        proposal = await self.propose()
        await self.review(proposal, agree=False)
        proposal = await self.propose()
        value = self.review_value(proposal)
        value['objections'] = []
        with self.assertRaisesRegex(workspace.InputError, 'prior objection'):
            decisions.review(markdown(decisions.REVIEW_FIELDS, value, 'Review record'), proposal, {'boundary'})

    async def test_finished_delegate_releases_slot_after_confirmed_cleanup_only(self):
        task = self.runtime.add_task('task-' + 'a'*32, 'A delegated check', 'primary')
        ctx = context_fixture(self.runtime, 'delegate', task_id=task['task_id'])
        path = task['workspace']+'/NOTE.md'
        self.runtime.draft(ctx, path, '# Delivered delegate result')
        self.save_handoff(ctx)
        with self.assertRaisesRegex(jobs.JobError, 'No slot'):
            await self.propose()
        result = await self.runtime.control(ctx, 'finish_task', path)
        self.assertEqual(result['status'], 'retirement_pending')
        self.assertFalse(task.get('released'))
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        self.assertTrue(task['released'])
        proposal = await self.propose()
        self.assertEqual(len([t for t in self.state['tasks'].values() if not t.get('released')]), 2)
        await self.review(proposal)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state)

    async def test_uncertain_retirement_retains_capacity_and_missing_handoff_is_honest(self):
        task = self.runtime.add_task('task-' + 'a'*32, 'Unfinished calculation', 'primary')
        ctx = context_fixture(self.runtime, 'delegate', cleanup=False, task_id=task['task_id'])
        await self.runtime.control(self.primary, 'retire_task', task['task_id'])
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        self.assertFalse(task.get('released'))
        self.assertIn('unconfirmed', task['retirement_error'])
        self.assertTrue(self.state['admission_block'])
        self.assertFalse(ctx['record']['cleanup_ok'])

    async def test_frozen_immutable_delegate_evidence_is_accessible_without_sibling_permissions(self):
        delegate = self.runtime.add_task('task-' + 'a'*32, 'Private delegate result', 'primary')
        ctx = context_fixture(self.runtime, 'delegate', task_id=delegate['task_id'])
        path = delegate['workspace']+'/NOTE.md'
        self.runtime.draft(ctx, path, '# Private delegate snapshot\nFinite proof.')
        self.save_handoff(ctx)
        await self.runtime.control(ctx, 'finish_task', path)
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        document = next(d for d in self.state['documents'].values() if d['path'] == path)
        text = markdown(decisions.PROPOSAL_FIELDS, {'coverage': [{
            **self.coverage()[0], 'evidence': ['document:' + document['document_id']]}]},
            'Decision record', **{'Evidence and reproduction': '[Delegate](document:' + document['document_id'] + ')'})
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md', text)
        result = await self.runtime.control(self.primary, 'propose_complete', 'outputs/PROPOSAL.md')
        await self.runtime.turns[result['opponent_id']]
        entry = next(e for e in self.runtime.current_proposal()['packet']['evidence']
                     if e['source'].startswith('document:'))
        self.assertIn('Finite proof', (self.project/entry['path']).read_text())
        with self.assertRaises(jobs.JobError):
            self.runtime.documents.raw(result['opponent_id'], document['document_id'])
        opponent = self.opponent_context()
        with self.assertRaises(jobs.JobError):
            self.runtime.draft(opponent, entry['path'], 'tamper')
        self.assertIn('Finite proof', (self.project/entry['path']).read_text())

    async def corrected_retired_delegate(self):
        task = self.runtime.add_task('task-' + 'a'*32, 'A delegated boundary check', 'primary')
        ctx = context_fixture(self.runtime, 'delegate', task_id=task['task_id'])
        path = task['workspace'] + '/NOTE.md'
        self.runtime.draft(ctx, path, '# Delegate finding\nThe boundary is included.')
        self.save_handoff(ctx)
        await self.runtime.control(ctx, 'finish_task', path)
        await asyncio.gather(*self.runtime.lifecycle_tasks)
        # Publication requires every writer to stop; use the real rollover path
        # with the existing labelled native checkpoint/context doubles.
        await self.roll_primary()
        self.assertTrue(task['released'])
        self.assertIsNone(task['context_id'])
        self.assertEqual(ctx['record']['publication_conflicts'], [])
        document = next(self.state['documents'][i] for i in ctx['record']['document_ids']
                        if self.state['documents'][i]['path'] == path)
        self.assertEqual(workspace.file_digest(self.project/path), document['sha256'])
        human = '# Human correction\nThe boundary is excluded; the delegate conclusion is false.'
        (self.project/path).write_text(human)
        self.runtime.draft(self.primary, 'work/NOTE.md',
                           '# Primary synthesis\nThe human correction excludes the boundary. '
                           'The finite-domain result survives only on the restricted domain.')
        return ctx, path, document, human

    async def propose_delegate_source(self, path, document=None):
        if document:
            return await self.propose_document(document['document_id'])
        text = markdown(decisions.PROPOSAL_FIELDS, {
            'coverage': [{**self.coverage()[0], 'evidence': [path]}]},
            'Decision record', **{'Evidence and reproduction': '[Delegate](/project/' + path + ')'})
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md', text)
        result = await self.runtime.control(self.primary, 'propose_complete', 'outputs/PROPOSAL.md')
        await self.runtime.turns[result['opponent_id']]
        return self.runtime.current_proposal(result['proposal']['version'])

    async def assert_retired_correction_review(self, snapshot):
        ctx, path, document, human = await self.corrected_retired_delegate()
        old = self.runtime.documents.raw('primary', document['document_id'])
        with self.assertRaisesRegex(jobs.JobError, 'Incorporate current human edit'):
            await self.propose_delegate_source(path, document if snapshot else None)
        with self.assertRaises(jobs.JobError):
            self.runtime.draft(self.primary, path, 'Cannot overwrite the delegate')
        await self.runtime.control(self.primary, 'incorporate_edit', path,
                                   parent='work/NOTE.md', sha256=workspace.file_digest(self.project/path))
        proposal = await self.propose_delegate_source(path, document if snapshot else None)
        frozen = {entry['source']: entry for entry in proposal['packet']['evidence']}
        self.assertEqual((self.project/frozen[path]['path']).read_text(), human)
        self.assertEqual((self.project/frozen['work/NOTE.md']['path']).read_bytes(),
                         self.runtime.effective_bytes('work/NOTE.md'))
        if snapshot:
            self.assertEqual((self.project/frozen['document:' + document['document_id']]['path']).read_bytes(), old)
        opponent_id = self.state['opposition']['opponent_id']
        with self.assertRaises(jobs.JobError):
            self.runtime.documents.raw(opponent_id, document['document_id'])
        await self.review(proposal)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))
        self.assertEqual((self.project/path).read_text(), human)
        self.assertEqual(self.runtime.documents.raw('primary', document['document_id']), old)
        self.assertEqual((ctx['drafts']/path).read_bytes(), old)
        self.assertIsNone(self.state['tasks'][ctx['record']['task_id']]['context_id'])

    async def test_primary_incorporates_retired_delegate_correction_for_document_review(self):
        await self.assert_retired_correction_review(snapshot=True)

    async def test_primary_incorporates_retired_delegate_correction_for_path_review(self):
        await self.assert_retired_correction_review(snapshot=False)

    async def test_retired_evidence_incorporation_rejects_changed_again_source_and_account(self):
        _, path, document, human = await self.corrected_retired_delegate()
        digest = workspace.file_digest(self.project/path)
        (self.project/path).write_text(human + '\nA second human correction.')
        with self.assertRaisesRegex(jobs.JobError, 'Human version changed'):
            await self.runtime.control(self.primary, 'incorporate_edit', path,
                                       parent='work/NOTE.md', sha256=digest)
        digest = workspace.file_digest(self.project/path)
        await self.runtime.control(self.primary, 'incorporate_edit', path,
                                   parent='work/NOTE.md', sha256=digest)
        self.runtime.draft(self.primary, 'work/NOTE.md', '# A different primary account')
        with self.assertRaisesRegex(jobs.JobError, 'source or primary account changed'):
            await self.propose_document(document['document_id'])
        await self.runtime.control(self.primary, 'incorporate_edit', path,
                                   parent='work/NOTE.md', sha256=digest)
        (self.project/path).write_text(human + '\nA third human correction.')
        with self.assertRaisesRegex(jobs.JobError, 'source or primary account changed'):
            await self.propose_delegate_source(path)
        self.assertFalse(self.state['opposition']['history'])
        # A human may also restore historical bytes. They become usable only
        # after explicit renewed incorporation of the actual canonical version.
        original = self.runtime.documents.raw('primary', document['document_id'])
        (self.project/path).write_bytes(original)
        with self.assertRaisesRegex(jobs.JobError, 'source or primary account changed'):
            await self.propose_document(document['document_id'])
        await self.runtime.control(self.primary, 'incorporate_edit', path,
                                   parent='work/NOTE.md', sha256=document['sha256'])
        proposal = await self.propose_document(document['document_id'])
        sources = {entry['source'] for entry in proposal['packet']['evidence']}
        self.assertTrue({path, 'work/NOTE.md', 'document:' + document['document_id']} <= sources)

    async def test_retired_evidence_incorporation_cannot_grant_foreign_authority(self):
        ctx, path, _, _ = await self.corrected_retired_delegate()
        digest = workspace.file_digest(self.project/path)
        for account in ('primary', path, 'AGENTS.md', 'outputs/MISSING.md'):
            with self.subTest(account=account), self.assertRaises((ValueError, OSError)):
                await self.runtime.control(self.primary, 'incorporate_edit', path,
                                           parent=account, sha256=digest)
        delegate = self.runtime.add_task('task-' + 'b'*32, 'Still working', 'primary')
        live = context_fixture(self.runtime, 'live-delegate', task_id=delegate['task_id'])
        live_path = delegate['workspace'] + '/NOTE.md'
        self.runtime.draft(live, live_path, '# Unfinished work')
        (self.project/live_path).write_text('# Human correction to unfinished work')
        with self.assertRaisesRegex(jobs.JobError, 'confirmed-retired'):
            await self.runtime.control(self.primary, 'incorporate_edit', live_path,
                                       parent='work/NOTE.md', sha256=workspace.file_digest(self.project/live_path))
        with self.assertRaisesRegex(jobs.JobError, 'owned by this task'):
            await self.runtime.control(live, 'incorporate_edit', path,
                                       parent='work/NOTE.md', sha256=digest)
        with self.assertRaises(jobs.JobError):
            await self.runtime.control(self.primary, 'incorporate_edit', 'starting_evidence/RESEARCH_QUESTIONS.md',
                                       parent='work/NOTE.md', sha256=workspace.file_digest(
                                           self.project/'starting_evidence/RESEARCH_QUESTIONS.md'))
        with self.assertRaises(jobs.JobError):
            await self.runtime.control(ctx, 'incorporate_edit', path, sha256=digest)
        self.assertNotIn('incorporated_evidence', self.state['tasks']['primary'])

    async def test_retired_correction_and_primary_account_are_bound_to_review_and_finalization(self):
        _, path, document, human = await self.corrected_retired_delegate()
        for index, change in enumerate(('source', 'account')):
            await self.runtime.control(self.primary, 'incorporate_edit', path,
                                       parent='work/NOTE.md', sha256=workspace.file_digest(self.project/path))
            proposal = await self.propose_document(document['document_id'])
            await self.review(proposal, identifier='opponent-' + str(index))
            if change == 'source':
                (self.project/path).write_text(human + '\nLater human correction.')
            else:
                self.runtime.draft(self.primary, 'work/NOTE.md', '# Later synthesis')
            with self.assertRaisesRegex(jobs.JobError, 'reassessment'):
                await self.finalize(proposal)
            self.assertTrue(proposal.get('invalidated'))
            self.assertFalse((self.project/'COMPLETE_ACK').exists())

    async def test_primary_incorporation_of_retired_evidence_survives_measured_rollover(self):
        _, path, document, human = await self.corrected_retired_delegate()
        result = await self.runtime.control(self.primary, 'incorporate_edit', path,
                                            parent='work/NOTE.md', sha256=workspace.file_digest(self.project/path))
        await self.roll_primary(identifier='successor-two')
        proposal = await self.propose_document(document['document_id'])
        self.assertEqual(proposal['observations'][path]['incorporation']['context_id'], result['context_id'])
        await self.review(proposal)
        await self.finalize(proposal)
        self.assertTrue(await self.runtime.shutdown_task, self.state.get('terminal_error'))
        self.assertEqual((self.project/path).read_text(), human)

    async def test_version_and_intent_binding_prevent_wrong_finalization(self):
        proposal = await self.propose()
        await self.review(proposal)
        for action, version in (('finalize_complete', '0'*64), ('finalize_stop', proposal['version']),
                                ('finalize_complete', None)):
            with self.assertRaises(jobs.JobError):
                await self.runtime.control(self.primary, action, 'outputs/FINAL.md', sha256=version)
        self.assertFalse(self.state['admission_block'])

    async def test_opponent_rollover_preserves_exact_review_history_in_successor_intake(self):
        proposal = await self.propose()
        await self.review(proposal, agree=False)
        proposal = await self.propose()
        opponent = self.opponent_context('opponent-before-rollover')
        task_id = opponent['record']['task_id']
        opponent['record']['native_thread_id'] = 'opponent-native'
        self.runtime.observe_context(opponent['record']['context_id'],
            params(thread='opponent-native'), provenance='injected-L4-55-percent-fixture')
        async def attach(task):
            successor = context_fixture(self.runtime, 'opponent-successor', task_id=task)
            successor['record'].update(native_thread_id='fresh-native', input_changes=[])
            return successor['record']['context_id']
        # Checkpoint turn is a double; all source/handoff/version logic is real.
        with patch.object(self.runtime, 'native_turn', AsyncMock()), patch.object(self.runtime, 'attach', attach):
            successor = await self.runtime.rollover(task_id, opponent['record']['context_id'])
        intake = self.runtime.successor_documents(task_id)
        self.assertEqual(intake['opposition']['opponent_id'], task_id)
        self.assertEqual(intake['opposition']['current'], proposal['id'])
        previous = intake['opposition']['history'][1]
        self.assertEqual(previous['review']['open_substantive_count'], 1)
        page = await self.runtime.control(self.runtime.contexts[successor], 'read_history',
                                          previous['id'], parent='review')
        self.assertIn('"id": "boundary"', page['content'])
        self.assertIn('validated_handoff', intake)
        self.assertEqual(successor, 'opponent-successor')

    async def test_concurrent_proposals_admit_one_opponent_only(self):
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md',
            markdown(decisions.PROPOSAL_FIELDS, {'coverage': self.coverage()}, 'Decision record',
                     **{'Evidence and reproduction': '[Code](/project/work/check.py)'}))
        results = await asyncio.gather(*(
            self.runtime.control(self.primary, 'propose_complete', 'outputs/PROPOSAL.md')
            for _ in range(2)), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(len(self.state['opposition']['history']), 1)
        self.assertEqual(sum(t['role'] == 'opponent' for t in self.state['tasks'].values()), 1)

    async def test_rollover_revokes_decision_queued_behind_job_admission(self):
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md',
            markdown(decisions.PROPOSAL_FIELDS, {'coverage': self.coverage()}, 'Decision record',
                     **{'Evidence and reproduction': '[Code](/project/work/check.py)'}))
        async with self.runtime.jobs.lock:
            work = asyncio.create_task(self.runtime.control(self.primary, 'propose_complete', 'outputs/PROPOSAL.md'))
            await asyncio.sleep(0)
            self.assertFalse(work.done())
            self.primary['record']['state'] = 'closing'
            self.state['tasks']['primary']['operational_state'] = 'checkpointing'
        with self.assertRaisesRegex(jobs.JobError, 'revoked attachment'):
            await work
        self.assertFalse(self.state['opposition']['history'])
        self.assertEqual(len(self.state['tasks']), 1)

    async def test_active_or_settling_jobs_block_freeze_without_spending_an_opponent_slot(self):
        entered = asyncio.Event()
        async def proposal():
            entered.set()
            return await self.propose()
        async with self.runtime.jobs.lock:
            work = asyncio.create_task(proposal())
            await entered.wait()
            await asyncio.sleep(0)
            self.assertFalse(work.done())
            self.state['jobs']['settling'] = {'job_id': 'settling', 'task_id': 'primary', 'state': 'reserved'}
        try:
            with self.assertRaisesRegex(jobs.JobError, 'active computations'):
                await work
            self.assertEqual(self.state['opposition']['history'], [])
            self.assertEqual(len(self.state['tasks']), 1)
        finally:
            self.state['jobs'].pop('settling')

    async def test_human_edit_cannot_be_hidden_by_primary_draft_at_freeze(self):
        (self.project/'work/NOTE.md').write_text('# Human correction')
        with self.assertRaisesRegex(jobs.JobError, 'Incorporate current human edit'):
            await self.propose()
        digest = workspace.file_digest(self.project/'work/NOTE.md')
        self.runtime.draft(self.primary, 'work/NOTE.md', '# Human correction incorporated with reasoning')
        await self.runtime.control(self.primary, 'incorporate_edit', 'work/NOTE.md', sha256=digest)
        proposal = await self.propose()
        self.assertEqual(proposal['observations']['work/NOTE.md']['canonical'], digest)

    async def test_rpc_disconnect_keeps_one_durable_proposal_and_revoked_context_cannot_finalize(self):
        self.runtime.draft(self.primary, 'outputs/PROPOSAL.md',
            markdown(decisions.PROPOSAL_FIELDS, {'coverage': self.coverage()}, 'Decision record',
                     **{'Evidence and reproduction': '[Code](/project/work/check.py)'}))
        directory = self.project/'.research_pipeline/rpc-fixture'
        directory.mkdir()
        self.primary['token'] = 'fixture-token'
        server = await isolation.control_server(lambda r, w: self.runtime.handle_rpc(self.primary, r, w), directory)
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        async def send(action):
            reader, writer = await asyncio.open_unix_connection(f'/proc/self/fd/{fd}/control.sock')
            writer.write((json.dumps({'token': 'fixture-token', 'operation': 'control',
                'arguments': {'action': action, 'path': 'outputs/PROPOSAL.md'}})+'\n').encode())
            await writer.drain()
            return reader, writer
        try:
            _, writer = await send('propose_complete')
            writer.close()
            await writer.wait_closed()
            async def recorded():
                while not self.state['opposition']['history']:
                    await asyncio.sleep(.01)
            await asyncio.wait_for(recorded(), 2)
            self.assertEqual(len(self.state['opposition']['history']), 1)
            self.primary['record']['state'] = 'closing'
            reader, writer = await send('finalize_complete')
            self.assertIn('Revoked or foreign', (await reader.readline()).decode())
            writer.close()
            await writer.wait_closed()
            self.assertFalse((self.project/'COMPLETE').exists())
        finally:
            server.close()
            await server.wait_closed()
            os.close(fd)
