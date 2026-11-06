"""Independent-process saved Source CAS and identical-delivery races with explicit readiness pipes."""

from dataclasses import replace
import json
import os
import select
import subprocess
import sys

from research_pipeline.domain import Submission
from research_pipeline.source import encode_envelope
from tests.source_cli_fixtures import SourceCliCase, CREATOR
from tests.test_source import known
from tests.test_vault import child_environment
from tests.tool_registration_fixtures import rows


class SourceCliConcurrencyTests(SourceCliCase):
    """Coordinate actual store handles at the sole submission boundary without timing assumptions."""

    def race(self, proposals):
        """Release two independently opened CLI stores only after both witness readiness; return outcomes."""
        children = []
        descriptors = []
        try:
            for proposal in proposals:
                ready_r, ready_w = os.pipe()
                go_r, go_w = os.pipe()
                descriptors.extend((ready_r, ready_w, go_r, go_w))
                argv = self.args('submit-source-capture', proposal=proposal)
                program = f'''
import os, runpy, sys
from research_pipeline.store import RecordStore
real = RecordStore.submit_typed

def submit(self, request):
    """Witness a ready independent handle, then enter the real transaction only on release."""
    os.write({ready_w}, b'R')
    os.close({ready_w})
    assert os.read({go_r}, 1) == b'G'
    os.close({go_r})
    return real(self, request)
RecordStore.submit_typed = submit
sys.argv = ['research_pipeline', *{argv!r}]
runpy.run_module('research_pipeline', run_name='__main__')
'''
                child = subprocess.Popen([sys.executable, '-B', '-c', program], cwd=self.parent,
                    env=child_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(ready_w, go_r))
                children.append((child, ready_r, go_w))
                os.close(ready_w)
                os.close(go_r)
                descriptors.remove(ready_w)
                descriptors.remove(go_r)
            for child, ready_r, _ in children:
                self.assertTrue(select.select([ready_r], [], [], 30)[0], 'missing submission readiness witness')
                self.assertEqual(os.read(ready_r, 1), b'R')
            for _, _, go_w in children:
                os.write(go_w, b'G')
            results = []
            for child, _, _ in children:
                out, err = child.communicate(timeout=45)
                results.append((child.returncode, out, err))
            return results
        finally:
            for fd in descriptors:
                os.close(fd)
            for child, _, _ in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)

    def test_distinct_requests_compete_for_exact_expected_head(self):
        """Exactly one new request commits; the loser reports CAS conflict with no second event or revision."""
        competing = Submission('competing-source', self.saved.provenance,
            [encode_envelope('capture', 2, replace(self.value, title=known('competing β')), CREATOR)], {'capture': 1})
        other = self.parent / 'other.json'
        from research_pipeline.source_capture import dumps_prepared_submission
        self.save(other, json.loads(dumps_prepared_submission(competing)))
        before = rows(self.root)
        results = self.race((self.proposal, other))
        self.assertEqual(sorted(r[0] for r in results), [0, 4])
        for status, out, err in results:
            if status == 0:
                receipt = json.loads(out)['result']['receipt']
                self.assertEqual(self.store.get_submission(receipt['submission_id']).to_dict(), receipt)
                self.assertEqual(err, b'')
            else:
                self.assertEqual(out, b'')
                self.assertEqual(json.loads(err)['code'], 'conflict')
        after = rows(self.root)
        for name in ('submissions', 'audit_events', 'revisions'):
            self.assertEqual(len(after[name]), len(before[name]) + 1)
        self.assertEqual(len(self.store.history('capture')), 2)

    def test_identical_delivery_returns_one_original_receipt(self):
        """Both handles acknowledge the same original commit and create no duplicate canonical effects."""
        before = rows(self.root)
        results = self.race((self.proposal, self.proposal))
        self.assertEqual([r[0] for r in results], [0, 0])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual([r[2] for r in results], [b'', b''])
        after = rows(self.root)
        for name in ('submissions', 'audit_events', 'revisions'):
            self.assertEqual(len(after[name]), len(before[name]) + 1)
        self.assertEqual(len(self.store.history('capture')), 2)
        self.result(self.args('submit-source-capture'))
        self.assertEqual(rows(self.root), after)
