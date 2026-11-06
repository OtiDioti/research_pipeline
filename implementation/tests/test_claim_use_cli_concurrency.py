"""Coherent old/new CLI snapshots across independent real writer and reader handles."""

import os
import select
import subprocess
import sys
import threading
from unittest.mock import patch

from research_pipeline.store import RecordStore
from tests.claim_use_fixtures import LIMITS, batch
from tests.test_claim_use_context import context_record
from tests.test_claim_use_cli import ClaimUseCliCase, COMMANDS, canonical
from tests.test_vault import child_environment


class ClaimUseCliConcurrencyTests(ClaimUseCliCase):
    """Pipes and events coordinate selected API reads; no production concurrency seam is introduced."""

    def test_both_cli_operations_retain_snapshot_while_writer_prepares_then_commits(self):
        """Opening validation is never the pause; release readers before requiring the blocked writer COMMIT."""
        for revision, command in enumerate(COMMANDS, 2):
            history = command == COMMANDS[1]
            before = (self.store.claim_use_history('use', limits=LIMITS) if history else
                      self.store.inspect_claim_use('use', limits=LIMITS)).to_dict()
            ready_read, ready_write = os.pipe()
            resume_read, resume_write = os.pipe()
            program = f'''
import os, runpy, sys
from research_pipeline import store as store_module, claim_use_store
from research_pipeline.store import RecordStore
active = False
paused = False
real_operation = getattr(RecordStore, {"claim_use_history" if history else "inspect_claim_use"!r})
real_transition = claim_use_store._transition

def pause():
    """Retain the genuine selected read transaction while a separate writer prepares SQL updates."""
    global paused
    if active and not paused:
        paused = True
        os.write({ready_write}, b"R")
        if os.read({resume_read}, 1) != b"G":
            raise RuntimeError("reader release missing")

def operation(self, *args, **kwargs):
    """Arm hooks only for the public operation, excluding lifetime validation during store opening."""
    global active
    active = True
    try:
        return real_operation(self, *args, **kwargs)
    finally:
        active = False

def fault(point):
    """Pause current inspection at its existing in-transaction bound-snapshot seam."""
    if point == "claim_use_inspection_after_binding" and not {history!r}:
        pause()

def transition(*args, **kwargs):
    """Pause history after constructing its first genuine transition in the retained page transaction."""
    result = real_transition(*args, **kwargs)
    if {history!r}:
        pause()
    return result
setattr(RecordStore, {"claim_use_history" if history else "inspect_claim_use"!r}, operation)
store_module._fault = fault
claim_use_store._transition = transition
sys.argv = ["research_pipeline", *{self.args(command)!r}]
runpy.run_module("research_pipeline", run_name="__main__")
'''
            prepared, reader_done = threading.Event(), threading.Event()
            failures = []
            def write():
                """Own a separate writer connection and let the prior read finish before COMMIT."""
                def barrier(point):
                    """Expose real prepared updates while waiting for the reader's acknowledged result."""
                    if point == 'after_claim_use_updates':
                        prepared.set()
                        if not reader_done.wait(15):
                            raise RuntimeError('reader did not finish before writer commit')
                try:
                    with RecordStore.open(self.root) as store:
                        with patch('research_pipeline.store._fault', barrier):
                            store.submit(batch('concurrent-'+str(revision), [context_record('support-evidence', revision)]))
                except BaseException as error:
                    failures.append(error)
                    prepared.set()
            process = subprocess.Popen([sys.executable, '-B', '-c', program], cwd=self.parent,
                env=child_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                pass_fds=(ready_write, resume_read))
            os.close(ready_write)
            os.close(resume_read)
            thread = threading.Thread(target=write)
            started = False
            try:
                readable, _, _ = select.select([ready_read], [], [], 15)
                self.assertTrue(readable, 'selected public operation never paused')
                self.assertEqual(os.read(ready_read, 1), b'R')
                thread.start()
                started = True
                self.assertTrue(prepared.wait(15))
                self.assertEqual(failures, [])
                os.write(resume_write, b'G')
                stdout, stderr = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertEqual(stderr, b'')
                result = dict(store=str(self.root), use_id='use')
                if history:
                    result.update(after_generation=0, page_limit=256)
                result['history' if history else 'inspection'] = before
                expected = dict(format='research_pipeline.cli_result', version=1, command=command, status='ok', result=result)
                self.assertEqual(stdout, canonical(expected))
            finally:
                reader_done.set()
                os.close(resume_write)
                os.close(ready_read)
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=10)
                if started:
                    thread.join(20)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])
            committed = self.equivalent(command)
            self.assertNotEqual(committed, before)
            self.assertEqual(self.store.head('support-evidence'), revision)
