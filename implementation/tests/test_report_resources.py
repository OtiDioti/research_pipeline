"""Selected-project resource projections with original receipts, uncertainty and exact source pins."""

import copy
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.domain import ArtifactReference, DomainValidationError, RecordReference
from research_pipeline.resources import ResourceInspectionLimitError, ResourceRequest
from research_pipeline.reports import ReportObservation, ReportRequest, ReportIntegrityError, ReportScopeError, render_report
from research_pipeline.store import RecordStore
from tests.report_fixtures import report_request, populate, ref
from tests.resource_fixtures import (
    root_request, allocation, reservation, observation, reconciliation, vector, LIMITS, scope,
)
from tests.test_reports import rehash
from tests.test_store import record, request


def record_run_scope(identity="run", revision=1):
    """Declare an exact record-scoped run, distinct from a similarly named controller identity."""
    return {"type": "record", "kind": "run", "reference": ref(identity, "run", "resource_scope", revision)}


def funded(store, *, private=False, sibling=False):
    """Fund a report-linked run/task/attempt and optionally interleave another project's private operation."""
    store.submit(request("tasks", [record("task", kind="task_specification")]))
    store.create_resource_account(root_request())
    if private:
        store.submit(request("private-project", [record("private", kind="project")]))
        doc = root_request(account_id="private", scope=scope("project", "private")).to_dict()
        doc.update(operation_id="private-op", receipt_id="private-receipt")
        doc["provenance"]["details"] = {"private_sentinel": "OTHER-PROJECT-SECRET"}
        doc["payload"]["policy"]["statement"] = "PRIVATE-POLICY-SECRET"
        store.create_resource_account(ResourceRequest.from_dict(doc))
    store.allocate_resources(allocation("run", "run", "project", scope=record_run_scope()))
    store.allocate_resources(allocation("task", "task", "run"))
    store.allocate_resources(allocation("attempt", "attempt", "task"))
    if sibling:
        store.allocate_resources(allocation("run", "sibling", "project"))
        store.reserve_resources(reservation("sibling-closeout", "sibling", "closeout", maxima=vector(local_time=3)))


class ReportResourceTests(unittest.TestCase):
    """Capture complete selected project accounting while preserving global snapshot version 2."""

    def setUp(self):
        """Allocate one private schema-3 store with exact scientific report roots."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "store"
        self.store = RecordStore.create(self.root, schema_version=3)
        self.addCleanup(self.store.close)
        populate(self.store)

    def test_no_account_and_controller_names_do_not_establish_run_linkage(self):
        """Distinguish no recorded account from zero usage and controller names from exact run scope."""
        self.store.commit_report(report_request())
        empty = self.store.read_report("report_initial").to_dict()["resources"]
        self.assertEqual(empty["accounts"], [])
        self.assertIn("No recorded", empty["scope"]["project_account"]["unknown_reason"])
        self.store.create_resource_account(root_request())
        self.store.allocate_resources(allocation("run", "run", "project"))
        self.store.commit_report(report_request("controller-run", 2))
        projected = self.store.read_report("controller-run").to_dict()["resources"]
        self.assertIn("controller", projected["scope"]["run_account"]["unknown_reason"])
        self.assertEqual(projected["scope"]["run_subtree"], [])
        self.assertEqual(projected["scope"]["controller_run_linkage"][0]["account_id"], "run")

    def test_project_scope_sequence_gaps_and_private_metadata_exclusion(self):
        """Retain sibling liabilities and original sequence gaps while excluding another project's payloads."""
        funded(self.store, private=True, sibling=True)
        self.store.reserve_resources(reservation(maxima=vector(tool_calls=10)))
        self.store.observe_resource_usage(observation(usage=vector(None, tool_calls=4)))
        self.store.commit_report(report_request())
        saved = self.store.read_report("report_initial")
        doc = saved.to_dict()
        resources = doc["resources"]
        self.assertEqual(resources["scope"]["project_account"], "project")
        self.assertEqual(resources["scope"]["run_account"], "run")
        self.assertEqual(resources["scope"]["run_subtree"], ["attempt", "run", "task"])
        sequences = [item["receipt"]["sequence"] for item in resources["operations"]]
        self.assertEqual(sequences[:2], [1, 3])
        self.assertEqual(resources["resource_sequence"], self.store.inspect_resources(limits=LIMITS).to_dict()["resource_sequence"])
        self.assertIn("sibling", [a["account_id"] for a in resources["accounts"]])
        self.assertNotIn("private", [a["account_id"] for a in resources["accounts"]])
        self.assertNotIn("OTHER-PROJECT-SECRET", saved._json)
        self.assertNotIn("PRIVATE-POLICY-SECRET", saved._json)
        self.assertEqual(doc["request"]["selection"], [])
        self.assertTrue(doc["root_categories"]["resource_evidence"])
        for mutation in ("receipt", "balance", "dependency", "duplicate_sequence"):
            bad = copy.deepcopy(doc)
            if mutation == "receipt":
                bad["resources"]["operations"][-1]["receipt"]["request_fingerprint"] = "0" * 64
            elif mutation == "balance":
                bad["resources"]["balances"][0]["dimensions"][0]["known_spent"] = "999"
            elif mutation == "dependency":
                bad["resources"]["operations"].pop(1)
            else:
                bad["resources"]["operations"][-1]["receipt"]["sequence"] = 1
            with self.subTest(mutation=mutation), self.assertRaises((DomainValidationError, ReportIntegrityError)):
                ReportObservation(rehash(bad))
        self.assertEqual(ReportObservation(doc), saved)
        limited = report_request("too-small", 2).to_dict()
        limited["limits"]["resources"]["max_operations"] = len(sequences)
        with self.assertRaises(ResourceInspectionLimitError):
            self.store.commit_report(ReportRequest(limited))

    def test_partial_conservative_authoritative_late_and_telemetry(self):
        """Retain dated reports/receipts through late liability, resettlement, reopen and exact restore."""
        funded(self.store)
        historical = self.store.put_artifact(b"Historical measured work\n")
        self.store.submit(request("measured-work", [record("work", artifact_references=[historical])]))
        stages = []

        from research_pipeline.report_capture import prepare_report_view
        from research_pipeline.vault import materialize_readable_view, inspect_readable_view
        from tests.test_report_publication import report_limits, navigation
        from tests.test_vault import restore_directories
        from tests.view_capture_fixtures import SOURCE
        self.addCleanup(restore_directories, self.root.parent)
        publications = {}

        def capture(identity, revision):
            """Commit at a controlled date and retain requests, receipts and all actual/generated bytes."""
            proposal = report_request(identity, revision, selection=[ref("work", "research_context")])
            observed_at = f"2026-11-{revision:02d}T12:00:00.000000Z"
            with patch("research_pipeline.report_capture.datetime") as clock:
                clock.now.return_value = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                result = self.store.commit_report(proposal)
            saved = self.store.read_report(identity)
            self.assertEqual(saved.to_dict()["observed_at"], observed_at)
            generated = render_report(saved)
            actual = {name: self.store.read_artifact(ArtifactReference.from_dict(artifact))
                      for name, artifact in result.to_dict()["artifacts"].items()}
            self.assertEqual(json.loads(actual["source.json"]), saved.to_dict())
            for name, data in generated.items():
                self.assertEqual(actual[name], data)
            resource_operations = self.store.inspect_resources(limits=LIMITS).to_dict()["operations"]
            stages.append((proposal, result, actual, generated, resource_operations))
            plan = prepare_report_view(self.store, identity, limits=report_limits())
            published = materialize_readable_view(self.store, plan, self.root.parent / ("published-" + identity),
                source_root=SOURCE, protected_roots=[], max_entries=10000)
            publications[identity] = (plan, Path(published.destination))
            navigation(Path(published.destination))
            return saved.to_dict()["resources"], generated

        def check_history(store):
            """Verify original IDs and every retained byte after later writes, reopening or restoration."""
            for proposal, result, actual, generated, operations in stages:
                identity = proposal.to_dict()["operation_id"]
                plan, published = publications[identity]
                self.assertEqual(prepare_report_view(store, identity, limits=report_limits()), plan)
                self.assertEqual(inspect_readable_view(published, limits=report_limits(), max_entries=10000).status, "verified")
                navigation(published)
                for prior_proposal, _, prior_actual, _, _ in stages:
                    revision = prior_proposal.to_dict()["report_revision"]
                    if revision <= proposal.to_dict()["report_revision"]:
                        for name, data in prior_actual.items():
                            self.assertEqual((published / "reports/runs/run" / str(revision) / name).read_bytes(), data)
                self.assertEqual(store.get_report_operation(identity), result)
                self.assertEqual(store.commit_report(proposal), result)
                self.assertEqual(store.get_submission(identity), result.receipt)
                self.assertEqual(render_report(store.read_report(identity)), generated)
                for name, artifact in result.to_dict()["artifacts"].items():
                    self.assertEqual(store.read_artifact(ArtifactReference.from_dict(artifact)), actual[name])
                for operation in operations:
                    self.assertEqual(store.get_resource_operation(operation["request"]["operation_id"]).to_dict(),
                                     operation["receipt"])
            self.assertEqual(store.read_artifact(historical), b"Historical measured work\n")

        self.store.reserve_resources(reservation(maxima=vector(model_calls=2, model_input_tokens=6, model_output_tokens=10, tool_calls=10),
            call_bounds={"max_input_tokens_per_call": 3, "max_output_tokens_per_call": 5}))
        self.store.observe_resource_usage(observation(usage=vector(None, tool_calls=4, model_calls=1, model_input_tokens=3, model_output_tokens=5),
            telemetry={"cached_input_tokens": 2, "reasoning_output_tokens": 3}))
        resources, old_bytes = capture("report_initial", 1)
        usage = resources["reservation_usage"][0]
        tool = next(d for d in usage["dimensions"] if d["dimension_id"] == "dim_tool_calls")
        self.assertEqual((tool["known_spent"], tool["remaining_reserved"], tool["charged_total"], tool["actual_usage"]), ("4", "6", "10", None))
        inputs = next(d for d in usage["dimensions"] if d["dimension_id"] == "dim_model_input_tokens")
        self.assertEqual(inputs["known_spent"], "3")
        conservative_receipt = self.store.reconcile_resource_usage(reconciliation("conservative", mode="conservative", observation_operation_id="op_partial"))
        resources, _ = capture("report-conservative", 2)
        conservative = resources["reservation_usage"][0]
        self.assertEqual(conservative["status"], "conservative")
        tool = next(d for d in conservative["dimensions"] if d["dimension_id"] == "dim_tool_calls")
        self.assertEqual((tool["conservative_excess"], tool["remaining_reserved"], tool["actual_usage"]), ("6", "0", None))
        self.store.observe_resource_usage(observation("complete", event="authoritative_completion",
            usage=vector(tool_calls=6, model_calls=1, model_input_tokens=3, model_output_tokens=5),
            telemetry={"cached_input_tokens": 2, "reasoning_output_tokens": 3}))
        settled = self.store.reconcile_resource_usage(reconciliation(previous=conservative_receipt.to_dict()["operation_id"]))
        resources, _ = capture("report-final", 3)
        final = resources["reservation_usage"][0]
        self.assertEqual(final["status"], "authoritative")
        tool = next(d for d in final["dimensions"] if d["dimension_id"] == "dim_tool_calls")
        self.assertEqual((tool["actual_usage"], tool["charged_total"]), ("6", "6"))

        # This distinct cumulative receipt arrives AFTER authoritative settlement.
        late = self.store.observe_resource_usage(observation("late", usage=vector(None, tool_calls=7)))
        resources, rendered = capture("report-reopened", 4)
        machine = json.loads(rendered["continuation.json"])
        projected = machine["groups"]["dimensioned_resources_and_stopping_decision"]["resources"]
        self.assertEqual(projected, resources)
        usage = projected["reservation_usage"][0]
        self.assertEqual(usage["status"], "unresolved")
        self.assertEqual(usage["latest_receipt_operation_id"], late.to_dict()["operation_id"])
        tool = next(d for d in usage["dimensions"] if d["dimension_id"] == "dim_tool_calls")
        self.assertEqual((tool["known_spent"], tool["remaining_reserved"], tool["charged_total"], tool["actual_usage"]),
                         ("7", "3", "10", None))
        breach = next(b for b in projected["breaches"] if b["reason"] == "post_settlement_usage")
        self.assertEqual((breach["observed"], breach["limit"]), ("7", "6"))
        self.assertTrue(all(balance["admission_blocked"] for balance in projected["balances"]))
        markdown = rendered["report.md"].decode()
        for phrase in ('"status": "unresolved"', '"known_spent": "7"', '"remaining_reserved": "3"',
                       '"charged_total": "10"', '"actual_usage": null', '"reason": "post_settlement_usage"',
                       '"observed": "7"', '"limit": "6"', '"admission_blocked": true'):
            self.assertIn(phrase.replace(": ", ":"), markdown)
        self.store.observe_resource_usage(observation("complete-again", event="authoritative_completion",
            usage=vector(tool_calls=7, model_calls=1, model_input_tokens=3, model_output_tokens=5),
            telemetry={"cached_input_tokens": 2, "reasoning_output_tokens": 3}))
        self.store.reconcile_resource_usage(reconciliation("settled-again", observation_operation_id="op_complete-again",
            previous=settled.to_dict()["operation_id"]))
        resources, rendered = capture("report-resettled", 5)
        final = resources["reservation_usage"][0]
        self.assertEqual(final["status"], "authoritative")
        tool = next(d for d in final["dimensions"] if d["dimension_id"] == "dim_tool_calls")
        self.assertEqual((tool["actual_usage"], tool["charged_total"], tool["remaining_reserved"]), ("7", "7", "0"))
        self.assertIn(breach, resources["breaches"])
        self.assertTrue(all(balance["admission_blocked"] for balance in resources["balances"]))
        for kind, expected in (("model_input_tokens", "3"), ("model_output_tokens", "5")):
            dimension = next(d for d in final["dimensions"] if d["dimension_id"] == "dim_" + kind)
            self.assertEqual((dimension["actual_usage"], dimension["charged_total"]), (expected, expected))
        self.assertIn(b'"cached_input_tokens":2', rendered["report.md"])
        self.assertIn(b'"reasoning_output_tokens":3', rendered["report.md"])
        self.assertEqual(render_report(self.store.read_report("report_initial")), old_bytes)
        self.assertEqual(self.store.commit_report(stages[0][0]), self.store.get_report_operation("report_initial"))
        self.store.submit(request("later-science", [record("work", 2)], {"work": 1}))
        self.store.observe_resource_usage(observation("later-receipt", usage=vector(None, tool_calls=7)))
        check_history(self.store)
        backup = self.root.parent / "backup"
        create_backup(self.store, backup)
        inspect_backup(backup)
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            check_history(reopened)
        destination = self.root.parent / "restored"
        with restore_backup(backup, destination) as restored:
            # Exact restoration is inspected before any retry or other potential write.
            self.assertEqual((destination / "metadata.sqlite3").read_bytes(), (backup / "snapshot.sqlite3").read_bytes())
            check_history(restored)
            plan, _ = publications["report-resettled"]
            final_publication = materialize_readable_view(restored, plan, self.root.parent / "published-restored",
                source_root=SOURCE, protected_roots=[], max_entries=10000)
            navigation(Path(final_publication.destination))
            for proposal, _, actual, _, _ in stages:
                for name, data in actual.items():
                    self.assertEqual((Path(final_publication.destination) / "reports/runs/run" /
                        str(proposal.to_dict()["report_revision"]) / name).read_bytes(), data)

    def test_record_run_identity_retains_revision_and_cross_project_account_rejected(self):
        """Match stable run IDs across exact revisions and reject a selected run account under another project."""
        funded(self.store)
        self.store.submit(request("run-advance", [record("run", 2, kind="run",
            record_references=[RecordReference("project", 1, "project", "project")])], {"run": 1}))
        self.store.commit_report(report_request(run=ref("run", "run", "run", 2)))
        saved = self.store.read_report("report_initial").to_dict()
        run_account = next(a for a in saved["resources"]["accounts"] if a["account_id"] == "run")
        self.assertEqual(run_account["scope"]["reference"]["revision"], 1)
        self.assertEqual(saved["request"]["run"]["revision"], 2)
        other = self.root.parent / "other"
        with RecordStore.create(other, schema_version=3) as store:
            populate(store)
            store.submit(request("foreign-project", [record("foreign", kind="project")]))
            store.create_resource_account(root_request(account_id="foreign", scope=scope("project", "foreign")))
            store.allocate_resources(allocation("run", "run", "foreign", scope=record_run_scope()))
            with self.assertRaises(ReportScopeError):
                store.commit_report(report_request())

    def test_dimensioned_estimates_and_record_scoped_sibling_context(self):
        """Retain complete declared estimates without charging them and keep sibling runs ledger-only."""
        from tests.report_fixtures import text
        funded(self.store)
        self.store.submit(request("sibling-record", [record("sibling-record", kind="run",
            record_references=[RecordReference("project", 1, "project", "project")])]))
        self.store.allocate_resources(allocation("run", "sibling-account", "project", scope=record_run_scope("sibling-record")))
        doc = report_request().to_dict()
        doc["declarations"]["continuation"] = [{"priority": 1, "task": ref("task", "task_specification", "task"),
            "checkpoint": {"value": None, "unknown_reason": "No checkpoint"}, "dependencies": [],
            "expected_output": text("Draft"), "required_checks": text("Verification"), "required_authority": text(),
            "required_resources": {"account_id": "attempt", "estimates": vector(tool_calls=2)}}]
        self.store.commit_report(ReportRequest(doc))
        saved = self.store.read_report("report_initial").to_dict()
        self.assertEqual(saved["resources"]["reservations"], [])
        self.assertEqual(saved["request"]["declarations"]["continuation"], doc["declarations"]["continuation"])
        self.assertIn("sibling-record", [r["record_id"] for r in saved["root_categories"]["resource_evidence"]])
        self.assertNotIn("sibling-record", [r["record_id"] for r in saved["root_categories"]["scientific"]])
        for estimate in ({"account_id": "missing", "estimates": vector(tool_calls=2)},
                         {"account_id": "attempt", "estimates": [{"dimension_id": "dim_tool_calls", "quantity": 2}]}):
            bad = copy.deepcopy(doc)
            bad.update(operation_id="bad-estimate", report_revision=2)
            bad["declarations"]["continuation"][0]["required_resources"] = estimate
            with self.assertRaises((ReportScopeError, DomainValidationError)):
                self.store.commit_report(ReportRequest(bad))
        with self.assertRaises(ReportScopeError):
            self.store.commit_report(report_request("wrong-science", 2, selection=[ref("sibling-record", "run")]))
        tampered = copy.deepcopy(saved)
        tampered["resources"]["operations"][-1]["receipt"]["scientific_watermark_event_id"] = 999
        with self.assertRaises(ReportIntegrityError):
            ReportObservation(rehash(tampered))
