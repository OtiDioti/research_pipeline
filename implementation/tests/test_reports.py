"""Strict report codecs and real committed setup reports; no scientific acceptance claims."""

import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline.domain import ArtifactReference, DomainValidationError, RecordReference
from research_pipeline.reports import (
    ReportRequest, ReportObservation, ReportCommitResult, ReportIntegrityError, ReportLimitError,
    ReportScopeError, OUTCOMES, dumps_request, loads_request, dumps_observation, loads_observation,
    dumps_result, loads_result, render_report, manifest_id, source_id, unavailable,
)
from research_pipeline.snapshot import _canonical, SnapshotLimitError
from research_pipeline.store import RecordStore, SubmissionConflictError, RevisionConflictError, StoreLayoutError
from tests.report_fixtures import report_request, populate, ref, text
from tests.test_store import record, request


def rehash(value):
    """Rehash deliberately changed data so tests exercise semantic validation beyond digest checks."""
    value["snapshot_id"] = hashlib.sha256(_canonical({k: v for k, v in value.items() if k != "snapshot_id"}).encode("ascii")).hexdigest()
    return value


def boundary_request():
    """Build a valid request with provenance at the documented 32-container limit."""
    doc = report_request().to_dict()
    nested = "boundary provenance"
    # Request root + provenance object + details object + 29 lists = 32 containers.
    # The committed result's receipt wrapper makes the same provenance 33 containers.
    for _ in range(29):
        nested = [nested]
    doc["provenance"]["details"] = {"nested": nested}
    return ReportRequest(doc)


class ReportCodecTests(unittest.TestCase):
    """Reject malformed, oversized and forged report declarations at every public boundary."""

    def test_complete_provenance_and_normalized_byte_bound(self):
        """Require complete provenance, reject nested duplicates, and bound normalized timestamp bytes."""
        original = report_request().to_dict()
        for provenance in ({"actor": "a", "created_at": "2026-11-01T00:00:00Z"},
                           {**original["provenance"], "extra": 1},
                           {**original["provenance"], "details": []},
                           {**original["provenance"], "actor": True},
                           {**original["provenance"], "created_at": 1}):
            with self.subTest(provenance=provenance), self.assertRaises(DomainValidationError):
                ReportRequest({**original, "provenance": provenance})
        doc = copy.deepcopy(original)
        doc["provenance"]["details"] = {"nested": {"key": 1}}
        encoded = _canonical(doc).replace('"key":1', '"key":1,"key":2')
        with self.assertRaises(DomainValidationError):
            loads_request(encoded)
        doc["provenance"]["created_at"] = "2026-11-01T00:00:00Z"
        self.assertEqual(ReportRequest(doc).to_dict()["provenance"]["created_at"], "2026-11-01T00:00:00.000000Z")
        doc["provenance"]["details"] = {"padding": ""}
        doc["provenance"]["details"]["padding"] = "x" * (256 * 1024 - len(_canonical(doc)))
        self.assertEqual(len(_canonical(doc)), 256 * 1024)
        with self.assertRaises(ReportLimitError):
            ReportRequest(doc)
        with self.assertRaises(ReportLimitError):
            loads_request(_canonical(doc))

    def test_roundtrip_detachment_and_all_outcomes(self):
        """Retain exact unknowns and every attributed outcome without operational state promotion."""
        for label in OUTCOMES:
            doc = report_request().to_dict()
            doc["declarations"]["outcome"]["label"] = label
            value = ReportRequest(doc)
            self.assertEqual(loads_request(dumps_request(value)), value)
            doc["authors"].append("mutated")
            self.assertEqual(value.to_dict()["authors"], ["Synthetic author"])

    def test_closed_unions_fields_types_and_unicode(self):
        """Fail missing/unknown/duplicate fields, implicit selectors, coercions and surrogate text."""
        original = report_request().to_dict()
        variants = []
        for key in original:
            bad = copy.deepcopy(original)
            del bad[key]
            variants.append(bad)
        for value in (True, 1.0, "1", 0):
            variants.append({**original, "report_revision": value})
        variants.extend(({**original, "unknown": 1}, {**original, "version": True},
                         {**original, "context": None}, {**original, "start_baseline": {"record_id": "old"}},
                         {**original, "authors": ["\ud800"]}, {**original, "authors": []},
                         {**original, "selection": [ref("x", "claim"), ref("x", "claim", revision=2)]},
                         {**original, "run": ref("run", "project", "run")},
                         {**original, "selection": [{**ref("x", "claim"), "revision": None}]}))
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises((DomainValidationError, TypeError)):
                ReportRequest(bad)
        encoded = dumps_request(report_request())
        with self.assertRaises(DomainValidationError):
            loads_request(encoded.replace('"version":1', '"version":1,"version":1', 1))
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(DomainValidationError):
                loads_request(encoded.replace('"version":1', '"version":' + value))

    def test_bounds_known_attribution_and_forged_state(self):
        """Enforce practical list/text/byte/depth ceilings and revalidate forged frozen values."""
        for update in ({"authors": ["a"] * 33}, {"authors": ["x" * 4097]},
                       {"selection": [ref("id" + str(i), "claim") for i in range(129)]}):
            with self.assertRaises(DomainValidationError):
                report_request(**update)
        doc = report_request().to_dict()
        doc["declarations"]["objective"]["attribution"] = unavailable("No author")
        with self.assertRaises(DomainValidationError):
            ReportRequest(doc)
        doc = report_request().to_dict()
        doc["limits"]["max_source_bytes"] = 64 * 1024 * 1024 + 1
        with self.assertRaises(ReportLimitError):
            ReportRequest(doc)
        doc = report_request().to_dict()
        doc["declarations"]["gaps"] = [text("a" * 4096)] * 128
        with self.assertRaises(ReportLimitError):
            ReportRequest(doc)
        doc = report_request().to_dict()
        nested = []
        for _ in range(33):
            nested = [nested]
        doc["provenance"]["details"] = {"nested": nested}
        with self.assertRaises(DomainValidationError):
            ReportRequest(doc)
        forged = report_request()
        object.__setattr__(forged, "_json", '{"format":"forged"}')
        with self.assertRaises(DomainValidationError):
            dumps_request(forged)
        class Impostor(ReportRequest):
            """Exercise exact-class public boundary rejection without alternate serialization."""
        with self.assertRaises(DomainValidationError):
            dumps_request(Impostor(report_request().to_dict()))

    def test_continuation_and_declaration_unions(self):
        """Exercise exact plans, checkpoints, unknown estimates, results, jobs and issues."""
        doc = report_request().to_dict()
        decl = doc["declarations"]
        decl["stop_reason"] = unavailable("No operational stop declaration")
        decl["interpretation"] = unavailable("No authored interpretation")
        decl["results"] = [{"statement": text("Unverified result"), "supporting_references": [ref("e", "evidence")]}]
        decl["completed_checks"] = [{"evidence": ref("e", "evidence", "reported_evidence"), "description": text("Synthetic check")}]
        decl["unresolved_issues"] = [text("Unresolved"), ref("issue", "issue", "unresolved_issue")]
        decl["saved_work"] = [{"manifest": ref("work", "work_product_manifest", "saved_work"), "description": text("Incomplete"), "state": "incomplete"}]
        decl["outstanding_jobs"] = [{"reference": ref("job", "attempt", "outstanding_job"), "description": text("Unknown job"), "state": "uncertain"}]
        item = {"priority": 1, "task": ref("task", "task_specification", "task"),
                "checkpoint": unavailable("No saved checkpoint"), "dependencies": [ref("e", "evidence")],
                "expected_output": text(), "required_checks": text(), "required_authority": text(),
                "required_resources": unavailable("No estimates supplied")}
        decl["continuation"] = [item]
        self.assertEqual(ReportRequest(doc).to_dict(), doc)
        for mutation in ([], [item, item], [{**item, "priority": True}], [{**item, "unexpected": 1}]):
            bad = copy.deepcopy(doc)
            bad["declarations"]["continuation"] = mutation
            with self.assertRaises(DomainValidationError):
                ReportRequest(bad)
        for field, key, value in (("results", "supporting_references", []), ("saved_work", "state", "complete"),
                                  ("outstanding_jobs", "state", "terminated"),
                                  ("completed_checks", "evidence", ref("job", "tool_execution", "reported_evidence"))):
            bad = copy.deepcopy(doc)
            bad["declarations"][field][0][key] = value
            with self.assertRaises(DomainValidationError):
                ReportRequest(bad)


class ReportCaptureTests(unittest.TestCase):
    """Use real source metadata and artifacts to verify saved observations and retry semantics."""

    def setUp(self):
        """Create one disposable private store and exact generic project/run scope."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "store"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)
        populate(self.store)

    def test_boundary_provenance_capture_codecs_and_original_id_recovery(self):
        """Preserve maximum-depth provenance and original bytes through commit, head advance and reopen."""
        proposal = boundary_request()
        request_doc = proposal.to_dict()
        self.assertEqual(ReportRequest.from_dict(request_doc), proposal)
        for encoded in (dumps_request(proposal), dumps_request(proposal).encode("utf-8")):
            self.assertEqual(loads_request(encoded), proposal)

        events_before = len(self.store.audit_events())
        result = self.store.commit_report(proposal)
        result_doc = result.to_dict()
        serialized = dumps_result(result)
        receipt = result.receipt
        self.assertEqual(ReportCommitResult(result_doc), result)
        self.assertEqual(ReportCommitResult.from_dict(result_doc), result)
        for encoded in (serialized, serialized.encode("utf-8")):
            decoded = loads_result(encoded)
            self.assertEqual(decoded, result)
            self.assertEqual(decoded.to_dict(), result_doc)
            self.assertEqual(decoded.receipt, receipt)
        self.assertEqual(receipt.provenance.to_dict(), request_doc["provenance"])
        self.assertEqual(self.store.get_submission("report_initial"), receipt)
        self.assertEqual(receipt.revisions, ((source_id("report_initial"), 1), (manifest_id("run"), 1)))
        for identity, revision in receipt.revisions:
            persisted = self.store.get_revision(identity, revision)
            self.assertEqual(persisted.provenance, receipt.provenance)
        self.assertEqual(len(self.store.audit_events()), events_before + 1)

        observation = self.store.read_report("report_initial")
        self.assertEqual(observation.to_dict()["request"], request_doc)
        source_json = dumps_observation(observation)
        for encoded in (source_json, source_json.encode("utf-8")):
            self.assertEqual(loads_observation(encoded), observation)
        artifacts = {name: ArtifactReference.from_dict(value)
                     for name, value in result_doc["artifacts"].items()}
        saved_bytes = {name: self.store.read_artifact(artifact) for name, artifact in artifacts.items()}
        self.assertEqual(saved_bytes, {"source.json": source_json.encode("utf-8"), **render_report(observation)})

        later = self.store.commit_report(report_request("boundary_later", 2))
        self.assertEqual(self.store.head(manifest_id("run")), 2)
        self.assertGreater(later.receipt.event_id, receipt.event_id)

        def check_original(store):
            """Verify original metadata, source and outputs without creating another audit event."""
            events = store.audit_events()
            for recovered in (store.get_report_operation("report_initial"), store.commit_report(proposal)):
                self.assertEqual(recovered, result)
                self.assertEqual(dumps_result(recovered), serialized)
                self.assertEqual(recovered.receipt, receipt)
            self.assertEqual(store.get_submission("report_initial"), receipt)
            recovered_source = store.read_report("report_initial")
            self.assertEqual(dumps_observation(recovered_source), source_json)
            self.assertEqual(render_report(recovered_source), render_report(observation))
            for name, artifact in artifacts.items():
                self.assertEqual(store.read_artifact(artifact), saved_bytes[name])
            self.assertEqual(store.audit_events(), events)

        check_original(self.store)
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            check_original(reopened)

    def test_adjacent_request_and_result_depth_rejections(self):
        """Reject one container beyond each bound, including forged canonical result state."""
        proposal = boundary_request()
        request_doc = proposal.to_dict()
        details = request_doc["provenance"]["details"]
        # One additional list makes the request 33 containers, beyond its unchanged limit.
        details["nested"] = [details["nested"]]
        for constructor in (ReportRequest, ReportRequest.from_dict):
            with self.assertRaises(DomainValidationError):
                constructor(request_doc)
        request_json = _canonical(request_doc)
        for encoded in (request_json, request_json.encode("utf-8")):
            with self.assertRaises(DomainValidationError):
                loads_request(encoded)

        result = self.store.commit_report(proposal)
        result_doc = result.to_dict()
        details = result_doc["receipt"]["provenance"]["details"]
        # The same extra list under the receipt makes this result 34 containers.
        details["nested"] = [details["nested"]]
        for constructor in (ReportCommitResult, ReportCommitResult.from_dict):
            with self.assertRaises(DomainValidationError):
                constructor(result_doc)
        result_json = _canonical(result_doc)
        for encoded in (result_json, result_json.encode("utf-8")):
            with self.assertRaises(DomainValidationError):
                loads_result(encoded)
        forged = ReportCommitResult.from_dict(result.to_dict())
        object.__setattr__(forged, "_json", result_json)
        with self.assertRaises(DomainValidationError):
            forged.to_dict()
        with self.assertRaises(DomainValidationError):
            dumps_result(forged)
        with self.assertRaises(DomainValidationError):
            _ = forged.receipt

    def test_empty_committed_report_and_pure_rendering(self):
        """Persist all seven truthful sections, then render without store, clock or external execution."""
        proposal = report_request()
        result = self.store.commit_report(proposal)
        observation = self.store.read_report("report_initial")
        self.assertEqual(loads_result(dumps_result(result)), result)
        self.assertEqual(loads_observation(dumps_observation(observation)), observation)
        rendered = render_report(observation)
        markdown = rendered["report.md"].decode()
        self.assertEqual(markdown.count("\n## "), 7)
        for phrase in ("Controller-generated state report", "No result was established", "Schema 2", "unknown", "unavailable", "not_yet_assessed", "never authorizes"):
            self.assertIn(phrase, markdown)
        doc = observation.to_dict()
        self.assertEqual(doc["scientific"]["watermark"]["event_id"], result.receipt.event_id - 1)
        with patch("research_pipeline.report_capture.datetime", side_effect=AssertionError("clock")), \
                patch.object(self.store, "read_artifact", side_effect=AssertionError("store")), \
                patch("subprocess.run", side_effect=AssertionError("process")), \
                patch("socket.socket", side_effect=AssertionError("network")), \
                patch("builtins.open", side_effect=AssertionError("filesystem")):
            self.assertEqual(render_report(observation), rendered)
        self.assertEqual(self.store.commit_report(proposal), result)
        self.assertEqual(self.store.get_report_operation("report_initial"), result)
        self.assertIsNone(self.store.get_report_operation("absent"))

    def test_defensive_observation_and_result_consumers(self):
        """Public codecs, rendering and receipt access reject subclasses and forged retained values."""
        result = self.store.commit_report(report_request())
        observation = self.store.read_report("report_initial")
        for value, encoder, decoder in ((result, dumps_result, loads_result),
                                        (observation, dumps_observation, loads_observation)):
            original = value.to_dict()
            detached = value.to_dict()
            detached["version"] = 99
            self.assertEqual(value.to_dict(), original)
            for replacement in (True, 1.0, 99):
                forged = type(value).from_dict(original)
                changed = {**original, "version": replacement}
                object.__setattr__(forged, "_json", _canonical(changed))
                with self.subTest(kind=type(value).__name__, version=replacement):
                    with self.assertRaises((DomainValidationError, ReportIntegrityError)):
                        encoder(forged)
                    with self.assertRaises((DomainValidationError, ReportIntegrityError)):
                        decoder(_canonical(changed))
                    with self.assertRaises((DomainValidationError, ReportIntegrityError)):
                        if type(value) is ReportObservation:
                            render_report(forged)
                        else:
                            _ = forged.receipt

        class ObservationSubstitute(ReportObservation):
            """Exercise rejection of inherited observation implementations at public boundaries."""

        class ResultSubstitute(ReportCommitResult):
            """Exercise rejection of inherited committed-result implementations at public boundaries."""

        for substitute, original, encoder in ((ObservationSubstitute, observation, dumps_observation),
                                              (ResultSubstitute, result, dumps_result)):
            value = substitute(original.to_dict())
            with self.assertRaises(DomainValidationError):
                encoder(value)
            with self.assertRaises(DomainValidationError):
                value.to_dict()
            with self.assertRaises(DomainValidationError):
                substitute.from_dict(original.to_dict())
        with self.assertRaises(DomainValidationError):
            render_report(ObservationSubstitute(observation.to_dict()))
        with self.assertRaises(DomainValidationError):
            _ = ResultSubstitute(result.to_dict()).receipt
        for value, encoder in ((observation, dumps_observation), (result, dumps_result),
                               (report_request(), dumps_request)):
            forged = type(value).from_dict(value.to_dict())
            object.__setattr__(forged, "_json", '{"format":"forged"}')
            # An instance override must not bypass retained-state validation.
            object.__setattr__(forged, "to_dict", value.to_dict)
            with self.assertRaises((DomainValidationError, ReportIntegrityError)):
                encoder(forged)
        changed = result.to_dict()
        changed["artifacts"]["report.md"] = {**changed["artifacts"]["source.json"],
                                             "size": changed["artifacts"]["source.json"]["size"] + 1}
        with self.assertRaises(ReportIntegrityError):
            ReportCommitResult(changed)
        for revision in (True, 1.0):
            changed = observation.to_dict()
            changed["source_bindings"][0]["revision"] = revision
            with self.assertRaises(DomainValidationError):
                ReportObservation(rehash(changed))

    def test_generic_evidence_selection_does_not_certify_completed_checks(self):
        """Keep generic Evidence descriptive unless a completed-check declaration requires typed evidence."""
        self.store.submit(request("generic-evidence", [record("opaque-evidence", kind="evidence",
            content={"claims_success": True})]))
        self.store.commit_report(report_request(selection=[ref("opaque-evidence", "evidence")]))
        output = json.loads(render_report(self.store.read_report("report_initial"))["continuation.json"])
        checks = output["groups"]["reported_checks_and_unresolved_issues"]
        self.assertEqual(checks["reported_completed_checks"], [])
        opaque = next(item for item in checks["unavailable_typed_interpretations"]
                      if item["record_id"] == "opaque-evidence")
        self.assertIsNone(opaque["typed_interpretation"]["value"])
        doc = report_request("false-completion", 2).to_dict()
        doc["declarations"]["completed_checks"] = [{"evidence": ref("opaque-evidence", "evidence", "reported_evidence"),
                                                    "description": text("Unsupported completion claim")}]
        with self.assertRaises(DomainValidationError):
            self.store.commit_report(ReportRequest(doc))

    def test_historical_pins_baseline_new_revision_and_unsafe_text(self):
        """Retain old revision/artifact pins and escape Markdown while comparing saved exact selections."""
        artifact = self.store.put_artifact(b"historical evidence bytes")
        self.store.submit(request("first-work", [record("work", artifact_references=[artifact])]))
        first_request = report_request(selection=[ref("work", "research_context")])
        first = self.store.commit_report(first_request)
        old_bytes = render_report(self.store.read_report("report_initial"))
        self.store.submit(request("next-work", [record("work", 2, record_references=[RecordReference("work", 1, "previous", "research_context")])], {"work": 1}))
        doc = report_request("report_later", 2, selection=[ref("work", "research_context", revision=2)],
                start_baseline=ref(manifest_id("run"), "work_product_manifest", "start_baseline")).to_dict()
        doc["declarations"]["objective"] = text("# INJECT\n[bad](https://invalid)\n```\n<script>")
        second = self.store.commit_report(ReportRequest(doc))
        observation = self.store.read_report("report_later")
        output = render_report(observation)
        changes = json.loads(output["continuation.json"])["groups"]["results_and_recorded_changes"]["recorded_changes"]
        self.assertIn(["work", 2], changes["added_exact_revisions"])
        self.assertNotIn(["work", 1], changes["no_longer_selected_exact_revisions"])
        self.assertIn({"record_id": "work", "old_revisions": [1], "new_revisions": [2]}, changes["selected_root_revisions"])
        self.assertNotIn(b"\n# INJECT", output["report.md"])
        event = self.store.get_revision(source_id("report_later"), 1)
        self.assertIn(artifact, event.artifact_references)
        self.assertEqual(self.store.commit_report(first_request), first)
        self.assertEqual(render_report(self.store.read_report("report_initial")), old_bytes)
        self.assertGreater(second.receipt.event_id, first.receipt.event_id)

    def test_scope_kind_cas_collision_and_typed_evidence_errors(self):
        """Reject wrong kinds, other project/run ownership, false checks, and report identity collisions."""
        self.store.submit(request("others", [record("other", kind="project"), record("foreign", kind="run",
            record_references=[RecordReference("other", 1, "project", "project")]),
            record("wrong-run", record_references=[RecordReference("foreign", 1, "run", "run")]),
            record("fake", kind="evidence")]))
        for proposal in (report_request(run=ref("foreign", "run", "run")),
                         report_request(selection=[ref("wrong-run", "research_context")]),
                         report_request(selection=[ref("other", "project")]),
                         report_request(selection=[ref("fake", "claim")])):
            with self.subTest(proposal=proposal), self.assertRaises(ReportScopeError):
                self.store.commit_report(proposal)
        doc = report_request().to_dict()
        doc["declarations"]["completed_checks"] = [{"evidence": ref("fake", "evidence", "reported_evidence"), "description": text("Cannot certify")}]
        with self.assertRaises(DomainValidationError):
            self.store.commit_report(ReportRequest(doc))
        self.store.commit_report(report_request())
        with self.assertRaises(RevisionConflictError):
            self.store.commit_report(report_request("competing"))
        with self.assertRaises(SubmissionConflictError):
            self.store.commit_report(report_request(authors=["Changed author"]))
        self.store.submit(request("generic", [record("arbitrary")]))
        with self.assertRaises(SubmissionConflictError):
            self.store.commit_report(report_request("generic", 2))

    def test_rehashed_semantic_forgeries_and_bounds(self):
        """Reject self-consistent hashes over altered roots, limits, source membership and qualifications."""
        self.store.commit_report(report_request())
        original = self.store.read_report("report_initial").to_dict()
        mutations = []
        bad = copy.deepcopy(original); bad["root_categories"]["scientific"] = []; mutations.append(bad)
        bad = copy.deepcopy(original); bad["qualifications"] = []; mutations.append(bad)
        bad = copy.deepcopy(original); bad["source_bindings"][0]["event_id"] = 999; mutations.append(bad)
        bad = copy.deepcopy(original); bad["request"]["limits"]["snapshot"]["max_roots"] += 1; mutations.append(bad)
        bad = copy.deepcopy(original); bad["resources"] = unavailable("Made up reason"); mutations.append(bad)
        for bad in mutations:
            with self.subTest(bad=bad), self.assertRaises((ReportIntegrityError, DomainValidationError)):
                ReportObservation(rehash(bad))
        for key in ("max_source_bytes", "max_output_file_bytes", "max_output_total_bytes"):
            doc = report_request("limited", 2).to_dict(); doc["limits"][key] = 1
            with self.subTest(key=key), self.assertRaises(ReportLimitError):
                self.store.commit_report(ReportRequest(doc))
        doc = report_request("limited", 2).to_dict(); doc["limits"]["snapshot"]["max_records"] = 1
        with self.assertRaises(SnapshotLimitError):
            self.store.commit_report(ReportRequest(doc))
        self.assertIsNone(self.store.get_report_operation("limited"))

    def test_schema_one_and_non_report_baselines_remain_unsupported(self):
        """Require migration and generated saved baselines without interpreting arbitrary old files."""
        from tests.legacy import create_legacy
        with create_legacy(self.parent / "legacy") as legacy:
            for action in (lambda: legacy.commit_report(report_request()),
                           lambda: legacy.get_report_operation("report_initial"),
                           lambda: legacy.read_report("report_initial")):
                with self.assertRaises(StoreLayoutError):
                    action()
        self.store.submit(request("old-file", [record("old-manifest", kind="work_product_manifest")]))
        with self.assertRaises((ReportIntegrityError, SubmissionConflictError)):
            self.store.commit_report(report_request(start_baseline=ref("old-manifest", "work_product_manifest", "start_baseline")))

    def test_every_outcome_renders_as_attributed_assessment(self):
        """Even objective_met/stopped retain explicit unavailable admission and operational stop verification."""
        for revision, label in enumerate(OUTCOMES, 1):
            doc = report_request("outcome-" + label, revision).to_dict()
            doc["declarations"]["outcome"]["label"] = label
            doc["declarations"]["stop_reason"] = text("Author reports stopping")
            self.store.commit_report(ReportRequest(doc))
            rendered = render_report(self.store.read_report(doc["operation_id"]))["report.md"].decode()
            self.assertIn(label, rendered)
            self.assertIn("Synthetic author", rendered)
            self.assertIn("Verified operational stopping unavailable", rendered)
            self.assertIn("Authenticated admission and authority unavailable", rendered)
            self.assertIn("No result was established", rendered)

    def test_unknown_generic_content_and_declaration_bounds(self):
        """Preserve opaque unsupported records while rejecting oversized per-entry reference collections."""
        self.store.submit(request("opaque", [record("opaque", content={"format": "unsupported", "version": 99, "claims_success": True})]))
        proposal = report_request(selection=[ref("opaque", "research_context")])
        self.store.commit_report(proposal)
        rendered = render_report(self.store.read_report("report_initial"))["report.md"]
        self.assertIn(b"Typed projection unavailable", rendered)
        doc = report_request("too-many", 2).to_dict()
        doc["declarations"]["results"] = [{"statement": text("Result"), "supporting_references": [ref("e" + str(i), "evidence") for i in range(33)]}]
        with self.assertRaises(DomainValidationError):
            ReportRequest(doc)
        doc = report_request("bad-result", 2).to_dict()
        doc["declarations"]["outcome"]["attribution"] = unavailable("Unknown author")
        with self.assertRaises(DomainValidationError):
            ReportRequest(doc)

    def test_selected_submission_membership_excludes_unrelated_batch_payload(self):
        """Verify original batch ordinal without embedding unrelated records or their private payloads."""
        self.store.submit(request("shared-batch", [record("unselected", content={"secret": "UNRELATED-BATCH-SECRET"}),
                                                   record("selected", content={"saved": True})]))
        self.store.commit_report(report_request(selection=[ref("selected", "research_context")]))
        doc = self.store.read_report("report_initial").to_dict()
        selected = next(b for b in doc["source_bindings"] if b["record_id"] == "selected")
        self.assertEqual(selected["ordinal"], 1)
        self.assertNotIn("UNRELATED-BATCH-SECRET", _canonical(doc))
        self.assertNotIn("unselected", [b["record_id"] for b in doc["source_bindings"]])
        self.store._connection.execute("UPDATE submissions SET fingerprint=? WHERE submission_id='shared-batch'", ("0" * 64,))
        with self.assertRaises(ReportIntegrityError):
            self.store.commit_report(report_request("damaged-binding", 2, selection=[ref("selected", "research_context")]))
