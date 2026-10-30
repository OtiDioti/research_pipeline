"""Saved Source captures across competing handles, process exits and exact backup restore."""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import unittest

from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.domain import RecordReference, Submission
from research_pipeline.source import decode_envelope, encode_envelope
from research_pipeline.source_capture import (
    dumps_prepared_submission, loads_prepared_submission, prepare_source_capture,
)
from research_pipeline.store import RecordStore, RevisionConflictError, SubmissionConflictError
from research_pipeline.work_product import encode_envelope as product_envelope
from tests import test_source_capture as capture_tests
from tests.test_assessment_store import metadata
from tests.test_source import known
from tests.test_store import CREATOR, CONTROLLER, request
from tests.test_work_product import manifest


class CaptureRecoveryTests(unittest.TestCase):
    """Reuse synthetic capture setup without inheriting or rediscovering the filesystem test suite."""

    setUp = capture_tests.CaptureTests.setUp
    entries = staticmethod(capture_tests.CaptureTests.entries)
    only = capture_tests.CaptureTests.only
    prepare = capture_tests.CaptureTests.prepare
    reject = capture_tests.CaptureTests.reject
    child = capture_tests.CaptureTests.child

    def save(self, submission, name="proposal.json"):
        """Exclusively save canonical request bytes outside input/runtime and sync file plus parent."""
        path = self.parent / name
        with path.open("xb") as stream:
            stream.write(dumps_prepared_submission(submission).encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return path

    def next_options(self, revision, **changes):
        """Declare an explicit immediate predecessor without discovering or silently rebasing heads."""
        meta = deepcopy(self.meta)
        meta["supersedes"] = RecordReference("capture", revision - 1, "supersedes", "source").to_dict()
        meta.update(changes)
        return dict(metadata=meta, revision=revision, expected_head=revision - 1,
                    submission_id="capture-" + str(revision))

    def test_independent_previews_one_cas_winner_and_used_id_refusal(self):
        """Two independent handles prepare without reservation; only one commits and inputs/history remain exact."""
        first = self.prepare()
        before = metadata(self.root)
        with RecordStore.open(self.root) as other:
            competing = prepare_source_capture(other, self.input, **{**self.options,
                "submission_id": "competing", "metadata": {**self.meta, "title": known("Other α").to_dict()}})
            self.assertEqual(metadata(self.root), before)
            receipt = self.store.submit_typed(loads_prepared_submission(self.save(first.submission).read_bytes()))
            self.reject(lambda: other.submit_typed(competing.submission), RevisionConflictError)
        error = self.reject(self.prepare, SubmissionConflictError)
        self.assertIn("retry the saved proposal directly", str(error))
        self.assertEqual(self.store.history("capture"), first.submission.records)
        self.assertEqual(self.store.get_submission("initial"), receipt)
        for name, payload in self.payloads.items():
            self.assertEqual((self.input / name).read_bytes(), payload)
        second = self.prepare(**self.next_options(2))
        self.store.submit_typed(second.submission)
        self.assertEqual(self.store.history("capture"), (*first.submission.records, *second.submission.records))

    def test_saved_exact_retry_after_edits_deletion_later_head_damage_and_restart(self):
        """Original-ID lookup precedes rereads, heads and artifact checks; changed reuse still conflicts."""
        prepared = self.prepare()
        saved = self.save(prepared.submission)
        frozen = saved.read_bytes()
        value = decode_envelope(prepared.submission.records[0])
        program = '''
import json, sys
from pathlib import Path
from research_pipeline.source_capture import loads_prepared_submission, dumps_prepared_submission
from research_pipeline.store import RecordStore
raw = Path(sys.argv[2]).read_bytes()
proposal = loads_prepared_submission(raw)
assert dumps_prepared_submission(proposal).encode('ascii') == raw
with RecordStore.open(sys.argv[1]) as store:
    print(json.dumps(store.submit_typed(proposal).to_dict()))
'''
        receipt = json.loads(self.child(program, self.root, saved))
        (self.input / "physical/α.tex").write_bytes(b"later selected edition")
        next_request = self.prepare(**self.next_options(2)).submission
        self.store.submit_typed(next_request)
        next_value = decode_envelope(next_request.records[0])
        self.assertEqual(self.store.read_artifact(value.originals[0].artifact), self.payloads["physical/α.tex"])
        self.assertEqual(self.store.read_artifact(next_value.originals[0].artifact), b"later selected edition")
        before = metadata(self.root)
        self.assertEqual(json.loads(self.child(program, self.root, saved)), receipt)
        self.assertEqual(metadata(self.root), before)
        # Inputs are caller-owned; deletion after capture must never enter retry ordering.
        for name in self.payloads:
            (self.input / name).unlink()
        self.assertEqual(json.loads(self.child(program, self.root, saved)), receipt)
        for reference, mode in ((value.originals[0].artifact, "missing"), (value.originals[1].artifact, "corrupt")):
            path = self.root / "objects" / reference.digest
            if mode == "missing":
                path.unlink()
            else:
                path.chmod(0o600)
                path.write_bytes(b"x" * reference.size)
                path.chmod(0o400)
            self.assertEqual(json.loads(self.child(program, self.root, saved)), receipt)
            self.assertEqual(metadata(self.root), before)
        self.assertEqual(saved.read_bytes(), frozen)
        for change in ("content", "order", "provenance", "submission-provenance", "acquisition"):
            changed, provenance, controller = value, CREATOR, CONTROLLER
            if change == "content":
                changed = replace(value, title=known("Changed"))
            elif change == "order":
                changed = replace(value, originals=value.originals[::-1])
            elif change == "provenance":
                provenance = CONTROLLER
            elif change == "submission-provenance":
                controller = CREATOR
            else:
                changed = replace(value, originals=[replace(value.originals[0],
                    provenance=replace(value.originals[0].provenance, notes=["Changed attribution declaration"])),
                    *value.originals[1:]])
            batch = Submission("initial", controller, [encode_envelope("capture", 1, changed, provenance)], {"capture": 0})
            self.reject(lambda: self.store.submit_typed(batch), SubmissionConflictError)
        self.assertEqual(len(self.store.audit_events()), 2)
        self.assertEqual(len(metadata(self.root)["submissions"]), 2)

    def test_real_exit_hot_journal_and_saved_request_reconciliation(self):
        """Real transaction exits distinguish rollback and lost acknowledgment, retaining bytes and inputs."""
        for boundary in ("before_metadata", "after_first_revision", "after_commit"):
            root = self.parent / ("runtime-" + boundary)
            with RecordStore.create(root) as store:
                # Many individually bounded strings make a real multi-megabyte
                # Source request, spilling pages without violating Source's cap.
                meta = {**deepcopy(self.meta), "limitations": [str(i) + "x" * 16000 for i in range(256)]}
                prepared = prepare_source_capture(store, self.input, **{**self.options,
                    "metadata": meta, "submission_id": boundary})
                before = metadata(root)
            saved = self.save(prepared.submission, boundary + ".json")
            self.child(r'''
import os, sys
from pathlib import Path
from research_pipeline import store as module
from research_pipeline.source_capture import loads_prepared_submission
proposal = loads_prepared_submission(Path(sys.argv[2]).read_bytes())
def fault(boundary):
    """Exit at the requested actual metadata boundary without Python cleanup."""
    if boundary == sys.argv[3]: os._exit(73)
module._fault = fault
with module.RecordStore.open(sys.argv[1]) as store:
    store.submit_typed(proposal)
raise AssertionError('fault not reached')
''', root, saved, boundary, expected=73)
            if boundary == "after_first_revision":
                journal = root / "metadata.sqlite3-journal"
                self.assertTrue(journal.exists())
                self.assertGreater(journal.stat().st_size, 512)
                self.assertNotEqual(journal.read_bytes()[:8], b"\0" * 8)
            for name, payload in self.payloads.items():
                self.assertEqual((self.input / name).read_bytes(), payload)
            for reference in prepared.submission.records[0].artifact_references:
                self.assertTrue((root / "objects" / reference.digest).exists())
            with RecordStore.open(root) as recovered:
                original = recovered.get_submission(boundary)
                if boundary == "after_commit":
                    self.assertIsNotNone(original)
                    self.assertEqual(recovered.history("capture"), prepared.submission.records)
                    committed = metadata(root)
                    self.assertEqual(recovered.submit_typed(loads_prepared_submission(saved.read_bytes())), original)
                    self.assertEqual(metadata(root), committed)
                    self.assertEqual(len(committed["submissions"]), 1)
                else:
                    self.assertIsNone(original)
                    self.assertEqual(metadata(root), before)
                    self.assertEqual(recovered.history("capture"), ())
            self.child(r'''
import sys
from pathlib import Path
from research_pipeline.source_capture import loads_prepared_submission
from research_pipeline.store import RecordStore
proposal = loads_prepared_submission(Path(sys.argv[2]).read_bytes())
with RecordStore.open(sys.argv[1]) as store:
    original = store.get_submission(proposal.submission_id)
    receipt = store.submit_typed(proposal)
    if original is not None: assert receipt == original
    assert store.submit_typed(proposal) == receipt
    assert store.head('capture') == 1
    assert len(store.audit_events()) == 1
    assert store.get_typed_revision('capture', 1)[0] == proposal.records[0]
''', root, saved)
            with RecordStore.open(root) as recovered:
                self.assertEqual(len(metadata(root)["submissions"]), 1)
                self.assertEqual(len(recovered.audit_events()), 1)
                for entry, payload in zip(capture_tests.capturing._inventory(decode_envelope(prepared.submission.records[0])),
                                           self.payloads.values()):
                    self.assertEqual(recovered.read_artifact(entry.artifact), payload)

    def test_actual_backup_exact_restore_history_uses_lineage_and_receipts(self):
        """Create/inspect/restore a real backup, then reopen and reconcile exact historical saved requests."""
        first = self.prepare().submission
        saved_first = self.save(first)
        receipt = self.store.submit_typed(first)
        value = decode_envelope(first.records[0])
        product = replace(manifest(value.originals[0].artifact), linked_sources=[
            RecordReference("capture", 1, "linked_source", "source")])
        historical_use = request("use", [product_envelope("use", 1, product, CREATOR)])
        use_receipt = self.store.submit_typed(historical_use)
        (self.input / "physical/α.tex").write_bytes(b"different synthetic edition")
        second = self.prepare(**self.next_options(2, title=known("Correction α").to_dict())).submission
        second_saved = self.save(second, "second.json")
        second_receipt = self.store.submit_typed(second)
        before = metadata(self.root)
        backup, destination = self.parent / "actual-backup", self.parent / "restored"
        create_backup(self.store, backup)
        info = inspect_backup(backup)
        self.assertEqual(info.schema_version, 2)
        with restore_backup(backup, destination) as restored:
            self.assertEqual(metadata(self.root), before)
            self.assertEqual(restored.history("capture"), (*first.records, *second.records))
            self.assertEqual(restored.get_revision("use", 1), historical_use.records[0])
            self.assertEqual(restored.get_submission("use"), use_receipt)
            self.assertEqual(restored.submit_typed(loads_prepared_submission(saved_first.read_bytes())), receipt)
            self.assertEqual(restored.submit_typed(loads_prepared_submission(second_saved.read_bytes())), second_receipt)
            for entry, payload in zip(capture_tests.capturing._inventory(value), self.payloads.values()):
                self.assertEqual(restored.read_artifact(entry.artifact), payload)
            self.assertEqual(restored.get_typed_revision("capture", 1)[1].extractions, value.extractions)
        restored_before = metadata(destination)
        self.child(r'''
import sys
from pathlib import Path
from research_pipeline.source_capture import loads_prepared_submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    for path in sys.argv[2:]:
        proposal = loads_prepared_submission(Path(path).read_bytes())
        assert store.submit_typed(proposal) == store.get_submission(proposal.submission_id)
    assert store.head('capture') == 2
    use = store.get_revision('use', 1)
    assert use.content['linked_sources'][0]['revision'] == 1
    first = store.get_typed_revision('capture', 1)[1]
    assert first.extractions[0].original_inputs == ('original', 'license')
    assert store.read_artifact(first.extractions[0].outputs[0].artifact) == b'Supplied extraction: x squared\n'
    assert len(store.audit_events()) == 3
''', destination, saved_first, second_saved)
        self.assertEqual(metadata(destination), restored_before)
        self.assertFalse(self.marker.exists())
