"""Actual passive Tool CLI mixed commits, exact reads and original receipt behavior."""

from copy import deepcopy
import json
from pathlib import Path

from research_pipeline.domain import RecordEnvelope, RecordReference, Submission
from research_pipeline.store import RecordStore
from tests.test_store import request, record
from tests.tool_assessment_store_fixtures import assessment, document, independent_projection
from tests.tool_assessment_fixtures import expected_artifacts, DIMENSIONS, known
from tests.tool_cli_fixtures import ToolCliCase, CREATOR, SUBMITTER, canonical
from tests.tool_registration_fixtures import changed, declaration, rows, tool


class ToolCliBehaviorTests(ToolCliCase):
    """Require complete subprocess results and independently observed durable metadata effects."""

    def test_mixed_forward_commit_exact_content_attributions_and_receipt(self):
        """Assessment-before-release commits preserve all supplied content and ordered identities."""
        self.config.chmod(0o400)
        self.batch.chmod(0o400)
        result = self.result()
        self.assertEqual(set(result), {"store", "batch", "submission_id", "receipt"})
        self.assertEqual(result["store"], str(self.root))
        self.assertEqual(result["batch"], str(self.batch))
        receipt = result["receipt"]
        self.assertEqual(set(receipt), {"submission_id", "fingerprint", "event_id", "committed_at", "provenance", "revisions"})
        self.assertEqual(receipt["revisions"], [["assessment", 1], ["tool", 1]])
        self.assertEqual(receipt["provenance"], SUBMITTER.to_dict())
        for item in self.saved.records:
            inspected = self.result(self.args("inspect-tool-record", kind=item.kind, record_id=item.record_id))
            self.assertEqual(set(inspected), {"store", "kind", "record_id", "revision", "envelope", "content", "commit", "direct_artifacts"})
            self.assertEqual(inspected["envelope"], item.to_dict())
            self.assertEqual(inspected["content"], item.content)
            self.assertEqual(inspected["commit"], {name: receipt[name] for name in ("submission_id", "committed_at", "fingerprint")})
            self.assertEqual(inspected["direct_artifacts"], {"status": "verified", "count": len(item.artifact_references)})
            self.assertEqual(inspected["envelope"]["provenance"], CREATOR.to_dict())
        self.assertNotEqual(CREATOR.actor, self.doc["attribution"]["actor"]["value"])
        self.assertEqual(self.doc["execution_permission"]["status"], "revoked")
        self.assertEqual([self.doc["qualification"][name]["outcome"] for name in DIMENSIONS], ["pass", "pass", "fail"])
        self.assertEqual(self.result()["receipt"], receipt)
        self.assertEqual(len(self.store.audit_events()), 1)
        observed = self.invoke(["inspect-receipt", "--config", str(self.config), "--submission-id", "cli-original"])
        self.assertEqual(json.loads(observed.stdout)["result"]["receipt"], receipt)

    def test_substantive_constrained_graph_and_reverse_order(self):
        """Non-Tool constrained prerequisites preexist; projected order follows an independent fixture oracle."""
        doc, batch = self.full_graph("full")
        self.store.submit_typed(request("prior-non-tool", batch[2:]))
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                identity = "full-" + str(reverse)
                release = declaration("release-" + str(reverse))
                selected = deepcopy(doc)
                selected["assessment_id"] = identity
                selected["target"] = dict(release=RecordReference(release.tool_id, 1, "assessed_release", "tool_release").to_dict(), release_id=release.release_id)
                members = [assessment(selected), tool(release)]
                if reverse:
                    members.reverse()
                saved = request("mixed-" + str(reverse), members)
                self.write_batch(saved)
                receipt = self.result()["receipt"]
                self.assertEqual(receipt["revisions"], [[item.record_id, 1] for item in members])
                result = self.result(self.args("inspect-tool-record", record_id=identity))
                expected = independent_projection()
                expected[0]["record_id"] = release.tool_id
                self.assertEqual(result["envelope"]["record_references"], expected)
                self.assertEqual(result["envelope"]["artifact_references"], expected_artifacts())
                self.assertEqual(result["content"], selected)
                self.assertEqual(result["envelope"]["provenance"]["actor"], "archivist")

    def test_single_kind_batches_reassessment_and_historical_exact_reads(self):
        """Each kind may be submitted alone; head advances do not change exact originals or their receipts."""
        first = self.result()["receipt"]
        altered_release = changed(self.release, release_label=known("later"))
        self.write_batch(Submission("release-next", SUBMITTER, [tool(altered_release, 2, CREATOR)], {"tool": 1}))
        self.result()
        revised = deepcopy(self.doc)
        revised["execution_permission"]["status"] = "denied"
        revised["environment"]["identity"] = known("separately declared new environment")
        self.write_batch(Submission("assessment-next", SUBMITTER, [assessment(revised, 2)], {"assessment": 1}))
        self.result()
        self.assertEqual(self.result(self.args("inspect-tool-record"))["content"], self.doc)
        self.assertEqual(self.result(self.args("inspect-tool-record", revision=2))["content"], revised)
        self.write_batch()
        before = rows(self.root)
        self.assertEqual(self.result()["receipt"], first)
        self.assertEqual(rows(self.root), before)

    def test_absence_wrong_selection_and_generic_local_meaning(self):
        """Explicit absence is silent status 3; coherent generic records remain locally inspectable only."""
        missing = self.invoke(self.args("inspect-tool-record"), expected=3)
        self.assertEqual(missing.stderr, b"")
        result = json.loads(missing.stdout)
        self.assertEqual(result["status"], "absent")
        self.assertEqual({key: result["result"][key] for key in ("envelope", "content", "commit", "direct_artifacts")},
                         dict.fromkeys(("envelope", "content", "commit", "direct_artifacts")))
        self.store.submit(self.saved)
        self.failure(5, argv=self.args("inspect-tool-record", kind="tool_release"), code="invalid_input")
        self.assertEqual(self.result(self.args("inspect-tool-record"))["content"], self.doc)
        self.invoke(self.args("inspect-tool-record", revision=2), expected=3)
        before = rows(self.root)
        receipt = self.store.get_submission(self.saved.submission_id).to_dict()
        self.assertEqual(self.result()["receipt"], receipt)
        self.assertEqual(rows(self.root), before)

    def test_exact_retry_precedes_heads_targets_and_bytes_after_damage(self):
        """Private guards prove original-ID reconciliation bypasses fresh availability and closure reads."""
        receipt = self.result()["receipt"]
        self.store.submit_typed(Submission("advance", SUBMITTER, [tool(self.release, 2, CREATOR)], {"tool": 1}))
        guard = '''
from research_pipeline.store import RecordStore
from research_pipeline.artifacts import ArtifactStore

def forbidden(*args, **kwargs):
    """Fail if a reconciled original attempts fresh target/history or artifact availability work."""
    raise AssertionError("fresh work during original-ID acknowledgement")
RecordStore._check_prepared_typed = forbidden
RecordStore._check_batch = forbidden
RecordStore._check_typed_targets = forbidden
ArtifactStore.verify = forbidden
'''
        self.assertEqual(self.result(prelude=guard)["receipt"], receipt)
        self.object_path(self.attachment).unlink()
        self.damage("UPDATE revisions SET content_json='{}' WHERE record_id='tool' AND revision=1")
        before = rows(self.root)
        self.assertEqual(self.result(prelude=guard)["receipt"], receipt)
        self.assertEqual(rows(self.root), before)
        self.failure(6, argv=self.args("inspect-tool-record"), code="integrity_error")
        # A changed, locally valid used ID conflicts even with damaged bytes.
        altered = Submission(self.saved.submission_id, SUBMITTER, [self.released, self.assessed], {"tool": 0, "assessment": 0})
        self.write_batch(altered)
        self.failure(4, code="conflict")
        self.assertEqual(rows(self.root), before)

    def test_inspection_does_not_traverse_pairing_or_hidden_history(self):
        """A coherent generic lookalike reads locally while fresh admission rejects its hidden graph atomically."""
        self.result()
        bad = deepcopy(self.doc)
        bad["assessment_id"] = "generic-bad-pair"
        bad["target"]["release_id"] = "sha256:" + "0" * 64
        original = assessment(bad)
        self.store.submit(request("generic-bad", [original]))
        self.assertEqual(self.result(self.args("inspect-tool-record", record_id=original.record_id))["content"], bad)
        consumer = document("consumer", self.release)
        consumer["lifecycle"]["supersedes"] = known([RecordReference(original.record_id, 1, "supersedes_assessment", "tool_assessment").to_dict()])
        self.write_batch(request("refused-hidden", [assessment(consumer)]))
        before = rows(self.root)
        self.failure(6, code="integrity_error")
        self.assertEqual(rows(self.root), before)
        self.damage("UPDATE revisions SET content_json='{}' WHERE record_id='tool' AND revision=1")
        self.assertEqual(self.result(self.args("inspect-tool-record"))["content"], self.doc)

    def test_malformed_generic_selected_content_and_direct_bytes(self):
        """Stored malformed/unsupported Tool wire never becomes generic success; missing/corrupt bytes fail."""
        self.result()
        for content in ({}, {"format": "unsupported", "version": 1}, {**self.doc, "version": 2}):
            with self.subTest(content=content.get("format")):
                self.damage("UPDATE revisions SET content_json=? WHERE record_id='assessment'", (canonical(content),))
                self.failure(6, argv=self.args("inspect-tool-record"), code="integrity_error")
        self.damage("UPDATE revisions SET content_json=? WHERE record_id='assessment'", (canonical(self.doc),))
        selected = self.object_path(self.attachment)
        selected.chmod(0o600)
        selected.write_bytes(b"X" * self.attachment.size)
        selected.chmod(0o400)
        self.failure(6, argv=self.args("inspect-tool-record"), code="integrity_error")
        selected.unlink()
        self.failure(6, argv=self.args("inspect-tool-record"), code="integrity_error")

    def test_fresh_mismatched_pair_stale_heads_and_missing_targets_are_atomic(self):
        """Store-owned refusal preserves every table, event, receipt and already published object."""
        self.result()
        cases = []
        mismatched = document("bad-pair", self.release)
        mismatched["target"]["release_id"] = "sha256:" + "0" * 64
        cases.append((request("bad-pair", [assessment(mismatched)]), 6))
        absent = document("absent-pin", declaration("absent-release"))
        cases.append((request("absent-pin", [assessment(absent)]), 6))
        cases.append((Submission("stale", SUBMITTER, [tool(self.release, 2)], {"tool": 0}), 4))
        for saved, status in cases:
            with self.subTest(submission=saved.submission_id):
                self.write_batch(saved)
                before = rows(self.root)
                self.failure(status, code="conflict" if status == 4 else "integrity_error")
                self.assertEqual(rows(self.root), before)
                self.assertIsNone(self.store.get_submission(saved.submission_id))
                self.assertEqual(self.store.read_artifact(self.attachment), b"inert CLI attachment\n")

    def test_replacement_pair_wrong_kind_and_invalid_release_history_refuse_atomically(self):
        """Reject a mismatched replacement pair, wrong target kind and damaged history without metadata effects."""
        self.result()
        # A distinct stable ID avoids self-replacement and reserves tool@2 for the history case.
        replacement_release = self.seed_release(declaration("replacement-tool"))
        replacement = deepcopy(self.doc)
        replacement["assessment_id"] = "replacement-bad"
        replacement["lifecycle"]["replacement"] = known({"release": RecordReference(replacement_release.tool_id, 1, "replacement_release", "tool_release").to_dict(),
                                                       "release_id": "sha256:" + "0" * 64})
        self.assertNotEqual(replacement["lifecycle"]["replacement"]["value"]["release_id"], replacement_release.release_id)
        self.write_batch(request("replacement-bad", [assessment(replacement)]))
        before = rows(self.root)
        self.failure(6, code="integrity_error")
        self.assertEqual(rows(self.root), before)
        self.store.submit(request("wrong-target-kind", [record("wrong-target", kind="decision")]))
        wrong = document("wrong-kind", self.release)
        wrong["target"]["release"]["record_id"] = "wrong-target"
        self.write_batch(request("wrong-kind", [assessment(wrong)]))
        before = rows(self.root)
        self.failure(6, code="integrity_error")
        self.assertEqual(rows(self.root), before)
        # Append a coherent generic current release, then damage its predecessor.
        self.store.submit(request("generic-advance", [tool(self.release, 2)], {"tool": 1}))
        self.damage("UPDATE revisions SET content_json='{}' WHERE record_id='tool' AND revision=1")
        self.assertEqual(self.result(self.args("inspect-tool-record", kind="tool_release", record_id="tool", revision=2))["content"], self.release.to_dict())
        consumer = document("history-consumer", self.release)
        consumer["target"]["release"]["revision"] = 2
        self.write_batch(request("history-consumer", [assessment(consumer)]))
        before = rows(self.root)
        self.failure(6, code="integrity_error")
        self.assertEqual(rows(self.root), before)

    def test_selected_release_bytes_and_metadata_only_transitive_closure(self):
        """Selected release direct bytes are verified; assessment closure does not require transitive release bytes."""
        from tests.test_tool_registration_recovery import with_artifact
        release = with_artifact("direct-release", self.attachment)
        self.write_batch(request("release-with-bytes", [tool(release)]))
        self.result()
        inspected = self.result(self.args("inspect-tool-record", kind="tool_release", record_id=release.tool_id))
        self.assertEqual(inspected["direct_artifacts"], {"status": "verified", "count": 1})
        self.object_path(self.attachment).unlink()
        self.failure(6, argv=self.args("inspect-tool-record", kind="tool_release", record_id=release.tool_id), code="integrity_error")
        doc = document("transitive", release)
        self.write_batch(request("transitive", [assessment(doc)]))
        self.result()
        inspected = self.result(self.args("inspect-tool-record", record_id="transitive"))
        self.assertEqual(inspected["direct_artifacts"], {"status": "verified", "count": 0})

    def test_schema_two_and_three_succeed_schema_one_is_not_migrated(self):
        """Explicit runtimes retain schema gating with no CLI creation or migration."""
        for version in (1, 2, 3):
            root = self.parent / ("schema-" + str(version))
            from tests.legacy import create_legacy
            with (create_legacy(root) if version == 1 else RecordStore.create(root, schema_version=version)) as store:
                store.put_artifact(b"inert CLI attachment\n")
                before = rows(root)
                self.config_value["store"] = str(root)
                self.save(self.config, self.config_value)
                if version == 1:
                    self.failure(5, code="invalid_input")
                    self.assertEqual(rows(root), before)
                else:
                    self.result()
                    self.result(self.args("inspect-tool-record"))
