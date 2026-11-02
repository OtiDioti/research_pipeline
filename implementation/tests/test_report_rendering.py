"""Retained negative typed labels and saved continuation declarations render without interpretation."""

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.domain import RecordReference
from research_pipeline.scientific import Evidence, decode_envelope, encode_envelope
from research_pipeline.reports import ReportRequest, ReportIntegrityError, ReportObservation, render_report, manifest_id, unavailable
from research_pipeline.store import RecordStore
from research_pipeline.work_product import encode_envelope as product_envelope
from tests.report_fixtures import populate, report_request, ref, text
from tests.test_assessment_store import mixed_graph, declarations
from tests.test_store import CREATOR, record, request
from tests.test_work_product import manifest
from tests.test_reports import rehash


class ReportRenderingTests(unittest.TestCase):
    """Verify observable saved labels, exact plans, empty outcomes and baseline source bindings."""

    def setUp(self):
        """Allocate an isolated default store with generic primary report roots."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = RecordStore.create(Path(temporary.name) / "runtime")
        self.addCleanup(self.store.close)
        populate(self.store)

    def test_negative_evidence_unfavorable_assessments_and_task_states(self):
        """Preserve negative/uncertain Evidence, disputed reviews, invalid routes and blocking issues."""
        artifact = self.store.put_artifact(b"negative synthetic observation")
        self.store.submit(request("generic-declarations", declarations()))
        graph = mixed_graph(artifact)
        for index, envelope in enumerate(graph):
            if envelope.kind == "evidence":
                evidence = replace(decode_envelope(envelope), result="NEGATIVE: property failed", origin="unverified",
                                   uncertainty_details=["Measurement remains uncertain"], failure_details=["Failed synthetic check"])
                graph[index] = encode_envelope(envelope.record_id, 1, evidence, CREATOR)
        self.store.submit_typed(request("assessments", graph))
        doc = report_request(selection=[ref("review-a", "review"), ref("review-b", "review"), ref("issue", "issue")]).to_dict()
        doc["declarations"]["completed_checks"] = [{"evidence": ref("evidence", "evidence", "reported_evidence"), "description": text("Reported negative check")}]
        doc["declarations"]["unresolved_issues"] = [ref("issue", "issue", "unresolved_issue"), text("No resolution asserted")]
        self.store.commit_report(ReportRequest(doc))
        output = render_report(self.store.read_report("report_initial"))["report.md"].decode()
        for phrase in ("NEGATIVE: property failed", "unverified", "Measurement remains uncertain", "Failed synthetic check",
                       "disputed", "requires_reassessment", "invalid", "blocking", "open", "provisional", "completed", "reported_completed_checks"):
            self.assertIn(phrase, output)
        self.assertEqual(self.store.get_revision("candidate", 1).scientific_disposition, "provisional")

    def test_saved_plan_checkpoint_incomplete_products_and_unknown_jobs(self):
        """Retain every ordered continuation field and declare job termination and estimates unavailable."""
        artifact = self.store.put_artifact(b"checkpoint bytes")
        self.store.submit(request("task-and-job", [record("task", kind="task_specification", operational_status="blocked"),
                                                   record("job", kind="tool_execution")]))
        content = replace(manifest(artifact), product_kind="checkpoint", run=RecordReference("run", 1, "run", "run"))
        self.store.submit_typed(request("checkpoint", [product_envelope("checkpoint", 1, content, CREATOR)]))
        doc = report_request().to_dict()
        declarations_value = doc["declarations"]
        declarations_value["saved_work"] = [{"manifest": ref("checkpoint", "work_product_manifest", "saved_work"), "description": text("Saved incomplete checkpoint"), "state": "checkpoint"}]
        declarations_value["outstanding_jobs"] = [{"reference": ref("job", "tool_execution", "outstanding_job"), "description": text("No termination evidence"), "state": "uncertain"}]
        plan = [{"priority": 2, "task": ref("task", "task_specification", "task"), "checkpoint": ref("checkpoint", "work_product_manifest", "checkpoint"),
                 "dependencies": [ref("job", "tool_execution")], "expected_output": text("A saved draft"), "required_checks": text("Independent verification"),
                 "required_authority": text(None, "No authenticated grant"), "required_resources": unavailable("No resource estimates saved")}]
        declarations_value["continuation"] = plan
        self.store.commit_report(ReportRequest(doc))
        output = render_report(self.store.read_report("report_initial"))
        machine = json.loads(output["continuation.json"])
        self.assertEqual(machine["continuation"], plan)
        self.assertEqual(machine["saved_work"], declarations_value["saved_work"])
        self.assertIn(b"No authenticated grant", output["report.md"])
        self.assertIn(b"No resource estimates saved", output["report.md"])
        self.assertIn(b"termination unavailable", output["report.md"])
        bad = report_request("bad-checkpoint", 2).to_dict()
        bad["declarations"]["saved_work"] = declarations_value["saved_work"]
        bad["declarations"]["saved_work"][0]["manifest"] = ref(manifest_id("run"), "work_product_manifest", "saved_work")
        with self.assertRaises(ReportIntegrityError):
            self.store.commit_report(ReportRequest(bad))

    def test_rehashed_baseline_cannot_replace_saved_start_observation(self):
        """A valid rehashed old document must still equal its captured manifest/source artifact binding."""
        self.store.commit_report(report_request())
        self.store.commit_report(report_request("later", 2, start_baseline=ref(manifest_id("run"), "work_product_manifest", "start_baseline")))
        doc = self.store.read_report("later").to_dict()
        baseline = doc["baseline"]["observation"]
        baseline["request"]["declarations"]["objective"] = text("Invented baseline")
        rehash(baseline)
        with self.assertRaises(ReportIntegrityError):
            ReportObservation(rehash(doc))

    def test_saved_reports_do_not_turn_old_ledger_dependencies_into_scientific_changes(self):
        """A declared saved report retains its full source but comparison excludes report-chain bookkeeping."""
        self.store.submit(request("old-scientific", [record("old-only")]))
        self.store.commit_report(report_request(selection=[ref("old-only", "research_context")]))
        doc = report_request("later-bookkeeping", 2,
            start_baseline=ref(manifest_id("run"), "work_product_manifest", "start_baseline")).to_dict()
        doc["declarations"]["saved_work"] = [{"manifest": ref(manifest_id("run"), "work_product_manifest", "saved_work"),
                                               "description": text("Retained prior report"), "state": "saved"}]
        self.store.commit_report(ReportRequest(doc))
        observation = self.store.read_report("later-bookkeeping")
        self.assertIn("old-only", [r["record_id"] for r in observation.to_dict()["scientific"]["records"]])
        output = json.loads(render_report(observation)["continuation.json"])
        changes = output["groups"]["results_and_recorded_changes"]["recorded_changes"]
        self.assertIn(["old-only", 1], changes["no_longer_selected_exact_revisions"])
        self.assertFalse(any(identity.startswith(("run-report-", "report-source-")) for identity, revision in changes["added_exact_revisions"]))
