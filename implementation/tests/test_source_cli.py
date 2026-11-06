"""Complete saved Source subprocess/API equivalence, offline isolation and original-ID recovery."""

from dataclasses import replace
import hashlib
import json
import os
import sqlite3

from research_pipeline.domain import RecordReference, Submission
from research_pipeline.source import encode_envelope
from research_pipeline.source_capture import dumps_prepared_submission, loads_prepared_submission
from research_pipeline.store import RecordStore
from tests.source_cli_fixtures import SourceCliCase, canonical, CREATOR, SUBMITTER
from tests.test_source import known, uninspected
from tests.tool_registration_fixtures import rows


class SourceCliTests(SourceCliCase):
    """Observe full documents and actual canonical history rather than adapter implementation details."""

    def test_inspection_complete_oracle_bytes_and_semantic_variants(self):
        """Whitespace/key order/escape differences change file SHA but preserve the entire decoded request."""
        before = rows(self.root)
        seen = set()
        fingerprints = set()
        for data in (self.proposal.read_bytes(), dumps_prepared_submission(self.saved).encode(),
                     json.dumps(self.wrapper, ensure_ascii=False, sort_keys=False).encode()):
            self.proposal.write_bytes(data)
            submission = loads_prepared_submission(data)
            fingerprint = hashlib.sha256(canonical(dict(fingerprint_version=1, submission=submission.to_dict())).encode()).hexdigest()
            domain = dict(proposal_path=str(self.proposal), proposal_sha256=hashlib.sha256(data).hexdigest(),
                          submission_fingerprint=fingerprint, proposal=json.loads(dumps_prepared_submission(submission)))
            expected = dict(format="research_pipeline.cli_result", version=1,
                            command="inspect-source-proposal", status="ok", result=domain)
            self.assertEqual(self.invoke().stdout, (canonical(expected) + "\n").encode())
            self.assertNotIn("input_root", domain)
            self.assertNotIn("mapping", domain)
            seen.add(domain["proposal_sha256"])
            fingerprints.add(fingerprint)
            self.assertEqual(self.proposal.read_bytes(), data)
            self.assertEqual(self.proposal.stat().st_mode & 0o7777, 0o600)
        self.assertEqual(len(seen), 3)
        self.assertEqual(len(fingerprints), 1)
        self.assertEqual(rows(self.root), before)

    def test_offline_absent_poisoned_runtime_and_no_scientific_access(self):
        """Inspection reads only selected controls/ancestor observations, despite poisoned scientific text."""
        missing = self.parent / "unavailable-runtime"
        self.save(self.config, {**self.config_value, "store": str(missing)})
        frozen = self.proposal.read_bytes()
        supplied = self.parent / 'supplied'
        supplied.mkdir(mode=0o700)
        os.mkfifo(supplied / 'input', 0o600)
        prelude = f'''
import builtins, os, socket
from research_pipeline import source_capture, artifacts, store, work_product_import, backup
from pathlib import Path

def forbidden(*args, **kwargs):
    """Fail any runtime/scientific/active operation during offline inspection."""
    raise AssertionError("forbidden protected operation")
store.RecordStore.open = forbidden
source_capture.prepare_source_capture = forbidden
work_product_import.prepare_work_product = forbidden
for name in ("get_revision", "get_typed_revision", "head", "history", "get_submission", "audit_events", "read_artifact", "submit_typed"):
    setattr(store.RecordStore, name, forbidden)
artifacts.ArtifactStore.open = forbidden
backup.inspect_backup = forbidden
socket.socket = forbidden
real_stat, real_open = os.stat, os.open

def stat(path, *args, **kwargs):
    """Refuse even availability probes of the configured unavailable runtime."""
    if str(path) in ({str(missing)!r}, 'unavailable-runtime', 'supplied/input'):
        forbidden()
    return real_stat(path, *args, **kwargs)

def open(path, *args, **kwargs):
    """Only controls and their ancestors can be opened by the offline adapter."""
    if str(path) in ({str(missing)!r}, 'unavailable-runtime', 'supplied/input'):
        forbidden()
    return real_open(path, *args, **kwargs)
os.stat, os.open = stat, open
'''
        self.assertEqual(self.result(prelude=prelude)["proposal"], self.wrapper)
        self.assertFalse(missing.exists())
        # An unavailable runtime can also be an unsafe symlink: offline inspection
        # must not touch it merely to test availability.
        missing.symlink_to(self.root)
        self.assertEqual(self.result(prelude=prelude)["proposal"], self.wrapper)
        self.assertEqual(self.proposal.read_bytes(), frozen)

    def test_complete_receipt_api_equivalence_history_and_reopened_retry(self):
        """Fresh CLI submission and original-ID reconciliation return the exact complete public receipt."""
        frozen = self.proposal.read_bytes()
        result = self.result(self.args("submit-source-capture"))
        receipt = self.store.submit_typed(loads_prepared_submission(frozen)).to_dict()
        self.assertEqual(result["receipt"], receipt)
        self.assertEqual(set(result), {"store", "proposal_path", "proposal_sha256", "submission_fingerprint", "receipt"})
        self.assertEqual(result["submission_fingerprint"], receipt["fingerprint"])
        self.assertEqual(self.store.get_typed_revision("capture", 2)[0].to_dict(), self.saved.records[0].to_dict())
        before = rows(self.root)
        self.assertEqual(self.result(self.args("submit-source-capture")), result)
        self.assertEqual(rows(self.root), before)
        self.assertEqual(self.proposal.read_bytes(), frozen)

    def test_retry_after_later_head_and_missing_or_corrupt_historical_objects(self):
        """No CLI or retry-side input/head/reference/artifact prereads precede the exact original request."""
        receipt = self.result(self.args("submit-source-capture"))["receipt"]
        later = replace(uninspected(), supersedes=RecordReference("capture", 2, "supersedes", "source"))
        self.store.submit_typed(Submission("later-capture", SUBMITTER,
            [encode_envelope("capture", 3, later, CREATOR)], {"capture": 2}))
        before = rows(self.root)
        prelude = f'''
from research_pipeline.store import RecordStore
from research_pipeline.source_capture import loads_prepared_submission
from pathlib import Path
expected = loads_prepared_submission(Path({str(self.proposal)!r}).read_bytes()).to_dict()
real = RecordStore.submit_typed
count = 0

def forbidden(*args, **kwargs):
    """Fail forbidden CLI prereads while preserving store-owned reconciliation."""
    raise AssertionError("CLI preread")
for name in ('head', 'history', 'get_revision', 'get_typed_revision', 'get_submission', 'audit_events', 'read_artifact', '_preview_typed_submission'):
    setattr(RecordStore, name, forbidden)

def submit(self, request):
    """Observe the actual call boundary and pass the unmodified request once."""
    global count
    count += 1
    assert count == 1 and request.to_dict() == expected
    return real(self, request)
RecordStore.submit_typed = submit
'''
        for damage in ("missing", "corrupt"):
            artifact = self.artifacts[0]
            path = self.root / "objects" / artifact.digest
            self.assertTrue(path.exists() or damage == "corrupt")
            if damage == "missing":
                path.unlink()
            else:
                path.write_bytes(b"wrong historical bytes")
                path.chmod(0o600)
            state = {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mode) for p in (self.root / "objects").rglob('*') if p.is_file()}
            self.assertEqual(self.result(self.args("submit-source-capture"), prelude=prelude)["receipt"], receipt)
            self.assertEqual(rows(self.root), before)
            self.assertEqual({str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mode) for p in (self.root / "objects").rglob('*') if p.is_file()}, state)
        changed = Submission(self.saved.submission_id, CREATOR, self.saved.records, self.saved.expected_heads)
        self.write_proposal(changed)
        self.failure(4, argv=self.args("submit-source-capture"), code="conflict")
        self.assertEqual(rows(self.root), before)

    def test_supported_schemas_and_schema_one_or_unknown_refusals(self):
        """Schemas 2–7 retain Source admission; legacy fresh refusal and unknown opening never migrate."""
        from tests.legacy import create_legacy
        for version in (1, 2, 3, 4, 5, 6, 7, 99):
            with self.subTest(schema=version):
                root = self.parent / ('schema-' + str(version))
                if version == 1:
                    store = create_legacy(root)
                    store.close()
                else:
                    with RecordStore.create(root, schema_version=2 if version == 99 else version):
                        pass
                if version == 99:
                    with sqlite3.connect(root / 'metadata.sqlite3') as connection:
                        connection.execute('PRAGMA user_version=99')
                self.save(self.config, {**self.config_value, 'store': str(root)})
                saved = Submission('schema-source', SUBMITTER, [encode_envelope('new', 1, uninspected(), CREATOR)], {'new': 0})
                self.write_proposal(saved)
                before = rows(root)
                if version in (1, 99):
                    self.failure(5, argv=self.args('submit-source-capture'), code='invalid_input' if version == 1 else 'unsafe_layout')
                    self.assertEqual(rows(root), before)
                else:
                    output = self.result(self.args('submit-source-capture'))
                    with RecordStore.open(root) as reopened:
                        self.assertEqual(output['receipt'], reopened.submit_typed(saved).to_dict())
                        self.assertEqual(reopened.history('new'), saved.records)

    def test_fresh_history_work_identity_cas_references_and_artifact_refusals(self):
        """Fresh invalid requests retain the store's exact admission guarantees, with no canonical effects."""
        before = rows(self.root)
        variants = [
            (replace(self.value, work_id='different-work'), 2, 1, 6, 'integrity_error'),
            (replace(self.value, supersedes=None), 2, 1, 6, 'integrity_error'),
            (replace(self.value, supersedes=RecordReference('capture', 2, 'supersedes', 'source')), 3, 2, 4, 'conflict'),
            (replace(self.value, reading=replace(self.value.reading, report=RecordReference('absent', 1, 'reading_report', 'work_product_manifest'))), 2, 1, 6, 'integrity_error'),
        ]
        for value, revision, head, status, code in variants:
            self.write_proposal(Submission('fresh-invalid', SUBMITTER,
                [encode_envelope('capture', revision, value, CREATOR)], {'capture': head}))
            self.failure(status, argv=self.args('submit-source-capture'), code=code)
            self.assertEqual(rows(self.root), before)
        self.write_proposal()
        # Shallow related/check declarations are not generalized into new
        # constrained targets by this adapter; the real fixture commits above.
        path = self.root / 'objects' / self.artifacts[0].digest
        path.unlink()
        self.failure(6, argv=self.args('submit-source-capture'), code='integrity_error')
        self.assertEqual(rows(self.root), before)
