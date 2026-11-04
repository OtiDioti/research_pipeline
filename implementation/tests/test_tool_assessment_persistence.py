"""Real passive assessment admission, ordered role coverage and exact metadata history."""

from copy import deepcopy
import json

from research_pipeline.snapshot import _classification
from research_pipeline.store import (
    RecordStore, SubmissionConflictError,
    _decode_typed_envelope,
)
from research_pipeline.tool_assessment import ToolAssessment
from tests.snapshot_fixtures import limits, simple_project, selection
from tests.test_store import record, request
from tests.test_typed_store import ref
from tests.tool_assessment_fixtures import DIMENSIONS, expected_artifacts, known, missing
from tests.tool_assessment_store_fixtures import (
    AssessmentCase, assessment, document, independent_projection,
)
from tests.tool_registration_fixtures import changed, declaration, rows, tool


class AssessmentPersistenceTests(AssessmentCase):
    """Persist passive reports without importing authority or interpreting reported outcomes."""

    def test_complete_projection_forward_mixed_batch_and_detached_inspection(self):
        """Every slot survives a forward mixed commit with independently specified projections."""
        doc, batch = self.full_graph()
        before = rows(self.root)
        submission = request("complete", batch)
        receipt = self.store.submit_typed(submission)
        selected, value = self.store.get_typed_revision("assessment", 1)
        self.assertIs(type(value), ToolAssessment)
        self.assertEqual(selected.to_dict(), batch[0].to_dict())
        self.assertEqual([pin.to_dict() for pin in selected.record_references], independent_projection())
        self.assertEqual([pin.to_dict() for pin in selected.artifact_references], expected_artifacts())
        self.assertEqual(value.to_dict(), doc)
        self.assertEqual(selected.provenance.actor, "archivist")
        self.assertNotEqual(doc["attribution"]["actor"]["value"], selected.provenance.actor)
        self.assertEqual(doc["execution_permission"]["status"], "revoked")
        self.assertEqual([doc["qualification"][name]["outcome"] for name in DIMENSIONS], ["pass", "pass", "fail"])
        changed_doc = value.to_dict()
        changed_doc["attribution"]["actor"]["value"] = "Changed reader copy"
        self.assertEqual(self.store.get_typed_revision("assessment", 1)[1].to_dict(), doc)
        after = rows(self.root)
        for table in before:
            if table not in {"identities", "revisions", "record_links", "artifact_links", "artifacts", "submissions", "audit_events"}:
                self.assertEqual(after[table], before[table], table)
        self.store.close()
        self.store = RecordStore.open(self.root)
        self.addCleanup(self.store.close)
        self.assertEqual(self.store.submit_typed(submission), receipt)
        self.assertEqual(self.store.get_typed_revision("assessment", 1)[1].to_dict(), doc)

    def test_pairing_and_replacement_are_exact_and_atomic(self):
        """Both declared release IDs must match exact content, including repeated release revisions."""
        release = self.seed_release()
        self.store.submit_typed(request("repeat", [tool(release, 2)], {"tool": 1}))
        doc = document()
        doc["lifecycle"]["replacement"] = known({"release": ref("tool", "replacement_release", "tool_release", 2).to_dict(),
                                                 "release_id": release.release_id})
        self.store.submit_typed(request("matching", [assessment(doc)]))
        for role in ("assessed_release", "replacement_release"):
            bad = deepcopy(doc)
            bad["assessment_id"] = "bad-" + role
            pair = bad["target"] if role == "assessed_release" else bad["lifecycle"]["replacement"]["value"]
            pair["release_id"] = "sha256:" + "0" * 64
            error = self.rejects(request(role, [assessment(bad)]))
            self.assertIn(role, str(error))
            self.assertIn(bad["assessment_id"] + "@1", str(error))
        # New explicit assessment revisions may target another release/environment.
        other = self.seed_release(declaration("other"))
        revised = document(release=other)
        revised["environment"]["identity"] = known("Explicit new environment")
        self.store.submit_typed(request("reassess", [assessment(revised, 2)], {"assessment": 1}))
        self.assertEqual(self.store.get_typed_revision("assessment", 1)[1].to_dict(), doc)
        self.assertEqual(self.store.get_typed_revision("assessment", 2)[1].to_dict(), revised)

    def test_both_batch_orders_and_unrelated_head_changes(self):
        """Forward overlay resolution and exact old pins do not depend on batch or head order."""
        for order in (False, True):
            release = declaration("release-" + str(order))
            item = assessment(document("assessment-" + str(order), release))
            batch = [item, tool(release)]
            self.store.submit_typed(request("order-" + str(order), list(reversed(batch)) if order else batch))
            amended = changed(release, release_label=known("amended"))
            self.store.submit_typed(request("advance-" + str(order), [tool(amended, 2)], {release.tool_id: 1}))
            next_doc = document("new-" + str(order), release)
            self.store.submit_typed(request("old-pin-" + str(order), [assessment(next_doc)]))
            self.assertEqual(self.store.get_typed_revision(item.record_id, 1)[1].to_dict()["target"]["release_id"], release.release_id)

    def test_each_role_missing_wrong_kind_and_constrained_generic_lookalikes(self):
        """All projected roles fail on absent exact pins/wrong kinds; constrained targets require codecs."""
        doc, batch = self.full_graph()
        self.store.submit(request("generic-graph", batch))
        for index, pin in enumerate(independent_projection()):
            with self.subTest(index=index, role=pin["relationship"]):
                original = rows(self.root)
                self.damage("UPDATE record_links SET target_revision=99 WHERE record_id='assessment' AND ordinal=?", (index,))
                # A coherent new owner constrained to this generic original must inspect its projection.
                consumer = document("consumer-" + str(index))
                consumer["lifecycle"]["supersedes"] = known([ref("assessment", "supersedes_assessment", "tool_assessment").to_dict()])
                self.rejects(request("invalid-" + str(index), [assessment(consumer)]))
                self.damage("UPDATE record_links SET target_revision=? WHERE record_id='assessment' AND ordinal=?", (pin["revision"], index))
                self.assertEqual(rows(self.root), original)
        # Exercise missing and wrong-kind exact targets with locally valid root projection.
        for index, pin in enumerate(independent_projection()):
            for mode in ("missing", "wrong-kind"):
                bad = deepcopy(doc)
                bad["assessment_id"] = f"{mode}-{index}"
                target_name = f"{mode}-target-{index}"
                def replace_pin(item):
                    """Change one supplied role occurrence without touching production projections."""
                    if type(item) is dict:
                        if item == pin:
                            item["record_id"] = target_name
                        else:
                            for child in item.values():
                                replace_pin(child)
                    elif type(item) is list:
                        for child in item:
                            replace_pin(child)
                replace_pin(bad)
                if mode == "wrong-kind":
                    self.store.submit(request(target_name, [record(target_name)]))
                self.rejects(request(f"reject-{mode}-{index}", [assessment(bad)]))

    def test_hidden_history_failures_for_successor_and_constrained_consumer(self):
        """A coherent latest revision cannot conceal invalid assessment metadata two steps back."""
        self.seed_release()
        for mode in ("pair", "replacement", "content", "provenance", "projection", "identity", "missing", "closure", "oversize", "noncanonical"):
            identity = "history-" + mode
            first = document(identity)
            if mode == "pair":
                first["target"]["release_id"] = "sha256:" + "0" * 64
            if mode == "replacement":
                replacement = self.seed_release(declaration(identity + "-replacement"))
                first["lifecycle"]["replacement"] = known({"release": ref(replacement.tool_id, "replacement_release", "tool_release").to_dict(),
                                                          "release_id": "sha256:" + "0" * 64})
            if mode == "closure":
                self.store.submit(request(identity + "-target", [record(identity + "-source", kind="source")]))
                first["environment"]["records"] = known([ref(identity + "-source", "assessed_environment", "source").to_dict()])
            self.store.submit(request(identity + "-1", [assessment(first)]))
            for revision in (2, 3):
                self.store.submit(request(f"{identity}-{revision}", [assessment(document(identity), revision)], {identity: revision - 1}))
            if mode == "content":
                self.damage("UPDATE revisions SET content_json='{}' WHERE record_id=? AND revision=1", (identity,))
            elif mode == "noncanonical":
                self.damage("UPDATE revisions SET content_json=' ' || content_json WHERE record_id=? AND revision=1", (identity,))
            elif mode == "provenance":
                self.damage("UPDATE revisions SET provenance_json=? WHERE record_id=? AND revision=1", ('{"actor":"author","created_at":"2026-10-30T10:00:00Z","details":{}}', identity))
            elif mode == "identity":
                bad = document("another")
                self.damage("UPDATE revisions SET content_json=? WHERE record_id=? AND revision=1", (json.dumps(bad, sort_keys=True, separators=(",", ":")), identity))
            elif mode == "projection":
                self.damage("DELETE FROM record_links WHERE record_id=? AND revision=1", (identity,))
            elif mode == "missing":
                self.damage("DELETE FROM revisions WHERE record_id=? AND revision=1", (identity,))
            elif mode == "oversize":
                self.damage("UPDATE revisions SET content_json=? WHERE record_id=? AND revision=1", ('x' * 4194305, identity))
            latest, value = self.store.get_typed_revision(identity, 3)
            self.assertEqual(value.to_dict(), document(identity))
            self.assertEqual(_classification(latest, _decode_typed_envelope)["category"], "locally_decoded")
            if mode == "pair":
                simple_project(self.store)
                snapshot = self.store.capture_snapshot(selection(identity), limits=limits())
                selected = next(item for item in snapshot.records if item["record_id"] == identity)
                self.assertEqual(selected["classification"]["category"], "locally_decoded")
                self.assertFalse(any(item["record_id"] == identity and item["revision"] < 3 for item in snapshot.records))
            # The original generic acknowledgment is distinct from fresh admission.
            before_retry = rows(self.root)
            saved = request(identity + "-3", [assessment(document(identity), 3)], {identity: 2})
            self.assertEqual(self.store.submit_typed(saved), self.store.get_submission(identity + "-3"))
            self.assertEqual(rows(self.root), before_retry)
            error = self.rejects(request(identity + "-4", [assessment(document(identity), 4)], {identity: 3}))
            self.assertIn(identity, str(error))
            consumer = document(identity + "-consumer")
            consumer["lifecycle"]["supersedes"] = known([ref(identity, "supersedes_assessment", "tool_assessment", 3).to_dict()])
            self.rejects(request(identity + "-consume", [assessment(consumer)]))

    def test_self_cross_cycles_and_shallow_then_constrained_cache_hits(self):
        """Descriptive cycles terminate; shallow cache occurrences cannot hide a constrained failure."""
        release = self.seed_release()
        docs = [document("a"), document("b")]
        for owner, other in zip(docs, reversed(docs)):
            owner["lifecycle"]["supersedes"] = known([
                ref(owner["assessment_id"], "supersedes_assessment", "tool_assessment").to_dict(),
                ref(other["assessment_id"], "supersedes_assessment", "tool_assessment").to_dict()])
        self.store.submit_typed(request("cycles", [assessment(doc) for doc in docs]))
        malformed = record("shared", kind="source", content={"format": "research_pipeline.source_content", "version": -1})
        self.store.submit(request("shallow", [malformed]))
        for order in (False, True):
            good = document("shallow-owner-" + str(order))
            good["environment"]["dependencies"] = known([{"name": "shared", "reported_version": missing(),
                "records": known([ref("shared", "assessed_dependency", "source").to_dict()]), "artifacts": known([]), "limitations": missing()}])
            bad = document("constrained-owner-" + str(order))
            bad["environment"]["records"] = known([ref("shared", "assessed_environment", "source").to_dict()])
            batch = [assessment(good), assessment(bad)]
            self.rejects(request("cache-" + str(order), list(reversed(batch)) if order else batch))
            self.store.submit_typed(request("only-shallow-" + str(order), [assessment(good)]))

    def test_generic_original_reconciliation_is_no_admission_certificate(self):
        """Local coherent inspection/retries acknowledge generic origins despite rejected fresh pairing."""
        self.seed_release()
        doc = document()
        doc["target"]["release_id"] = "sha256:" + "0" * 64
        original = request("generic-original", [assessment(doc)])
        receipt = self.store.submit(original)
        before = rows(self.root)
        self.assertEqual(self.store.submit_typed(original), receipt)
        self.assertEqual(rows(self.root), before)
        self.assertEqual(self.store.get_typed_revision("assessment", 1)[1].to_dict(), doc)
        self.assertEqual(_classification(original.records[0], _decode_typed_envelope)["category"], "locally_decoded")
        different = document("fresh")
        different["target"]["release_id"] = doc["target"]["release_id"]
        self.rejects(request("fresh", [assessment(different)]))
        changed_doc = deepcopy(doc)
        changed_doc["limitations"] = known(["changed but locally valid"])
        with self.assertRaises(SubmissionConflictError):
            self.store.submit_typed(request("generic-original", [assessment(changed_doc)]))
        self.assertEqual(rows(self.root), before)

    def test_selected_classification_categories_and_direct_artifact_precedence(self):
        """Snapshots classify explicit formats locally and never inspect implicit history or pairing."""
        self.seed_release()
        for name, payload, category in (("generic", {}, "generic"), ("unknown", {"format": "future"}, "unsupported"),
                ("version", {"format": "research_pipeline.tool_assessment_content", "version": 2}, "unsupported"),
                ("malformed", {"format": "research_pipeline.tool_assessment_content", "version": 1}, "malformed_typed")):
            item = record(name, kind="tool_assessment", content=payload)
            self.store.submit(request(name, [item]))
            self.assertEqual(_classification(item, _decode_typed_envelope)["category"], category)
        good = assessment()
        self.store.submit_typed(request("valid", [good]))
        simple_project(self.store)
        captured = self.store.capture_snapshot(selection("assessment"), limits=limits())
        self.assertIn("locally_decoded", str(captured.to_dict()))
        from research_pipeline.artifacts import ArtifactNotFoundError
        from research_pipeline.tool_assessment import ToolAssessmentValidationError
        artifact = self.store.put_artifact(b"selected direct attachment")
        malformed = record("malformed-with-object", kind="tool_assessment",
            content={"format": "research_pipeline.tool_assessment_content", "version": 1}, artifact_references=[artifact])
        self.store.submit(request("malformed-object", [malformed]))
        self.object_path(artifact).unlink()
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_typed_revision("malformed-with-object", 1)
        self.store.put_artifact(b"selected direct attachment")
        with self.assertRaises(ToolAssessmentValidationError):
            self.store.get_typed_revision("malformed-with-object", 1)

    def test_all_evidence_bases_kind_alternatives_in_every_enclosing_location(self):
        """Common evidence rules apply separately to checks, review/issue, permission, qualifications and lifecycle."""
        from tests.tool_assessment_fixtures import evidence, wire
        from tests.test_tool_registration import target
        doc, batch = self.full_graph()
        self.store.submit(request("generic-complete", batch))
        attachment = self.store.put_artifact(b"scientific evidence artifact")
        item, dependencies = target("scientific-evidence", "evidence", attachment)
        self.store.submit_typed(request("scientific-target", [item, *dependencies]))
        alternatives = (
            ("assessor_assertion", "reported_assertion", "source", "science_result"),
            ("assessor_assertion", "reported_assertion", "work_product_manifest", "definition_manifest"),
            ("assessor_assertion", "reported_assertion", "evidence", "scientific-evidence"),
            ("builder_self_test", "builder_self_test", "work_product_manifest", "interface_result"),
            ("builder_self_test", "builder_self_test", "evidence", "scientific-evidence"),
            ("reported_tool_execution", "reported_tool_execution", "tool_execution", "software_result"),
            ("independent_review", "independent_review", "review", "review"),
        )
        locations = ("check", "review", "issue", "permission", *DIMENSIONS, "lifecycle")
        for location in locations:
            for basis, role, kind, target_name in alternatives:
                identity = location + "-" + basis + "-" + kind
                value = document(identity)
                supplied = evidence("supplied", basis)
                supplied["records"] = known([ref(target_name, role, kind).to_dict()])
                supplied["artifacts"] = known([])
                if location == "check":
                    check = wire()["checks"]["value"][0]
                    check["basis"] = basis
                    check["definition_records"] = known([])
                    check["definition_artifacts"] = known([])
                    check["evidence"] = known([supplied])
                    value["checks"] = known([check])
                elif location in ("review", "issue"):
                    field = "reviews" if location == "review" else "issues"
                    entry = deepcopy(doc[field]["value"][0])
                    entry["evidence"] = known([supplied])
                    value[field] = known([entry])
                else:
                    report = (value["execution_permission"] if location == "permission" else
                              value["lifecycle"] if location == "lifecycle" else value["qualification"][location])
                    report["evidence"] = known([supplied])
                with self.subTest(location=location, basis=basis, kind=kind):
                    self.store.submit_typed(request(identity, [assessment(value)]))
                    restored = self.store.get_typed_revision(identity, 1)[1].to_dict()
                    self.assertEqual(restored, value)

    def test_constrained_alternatives_reject_lookalikes_and_invalid_deeper_closure(self):
        """Supported-looking payloads are neither sufficient nor a substitute for required typed closure."""
        self.seed_release()
        artifact = self.store.put_artifact(b"target bytes")
        from tests.test_tool_registration import target
        for kind in ("source", "work_product_manifest", "tool_release", "evidence", "issue"):
            for mode in ("generic", "unsupported", "malformed", "closure"):
                identity = kind + "-" + mode
                if mode == "closure":
                    item, dependencies = target(identity, kind, artifact, invalid_closure=True)
                else:
                    payload = {} if mode == "generic" else {"format": "future"} if mode == "unsupported" else {
                        "format": "research_pipeline." + ("scientific" if kind == "evidence" else "assessment" if kind == "issue" else "work_product" if kind == "work_product_manifest" else kind) + "_content", "version": 1}
                    item, dependencies = record(identity, kind=kind, content=payload), []
                self.store.submit(request(identity, [item, *dependencies]))
                doc = document("owner-" + identity)
                if kind in ("source", "work_product_manifest"):
                    doc["environment"]["records"] = known([ref(identity, "assessed_environment", kind).to_dict()])
                elif kind == "tool_release":
                    doc["lifecycle"]["replacement"] = known({"release": ref(identity, "replacement_release", kind).to_dict(), "release_id": "sha256:" + "0" * 64})
                elif kind == "issue":
                    from tests.tool_assessment_fixtures import wire
                    entry = wire()["issues"]["value"][0]
                    entry["issue"] = ref(identity, "reported_issue", kind).to_dict()
                    entry["evidence"] = known([])
                    doc["issues"] = known([entry])
                else:
                    from tests.tool_assessment_fixtures import evidence
                    supplied = evidence(identity)
                    supplied["records"] = known([ref(identity, "reported_assertion", kind).to_dict()])
                    supplied["artifacts"] = known([])
                    doc["lifecycle"]["evidence"] = known([supplied])
                with self.subTest(kind=kind, mode=mode):
                    self.rejects(request("reject-" + identity, [assessment(doc)]))

    def test_shallow_targets_ignore_malformed_content_and_missing_attachments(self):
        """Dependency, decision and execution references remain descriptive despite typed-looking garbage."""
        from tests.tool_assessment_fixtures import evidence
        self.seed_release()
        artifact = self.store.put_artifact(b"unavailable shallow bytes")
        targets = [record("shallow-" + kind, kind=kind, content={"format": "research_pipeline.operating_authority_content"},
                          artifact_references=[artifact]) for kind in ("source", "work_product_manifest", "tool_release", "decision", "tool_execution")]
        self.store.submit(request("shallow-prerequisites", targets))
        self.object_path(artifact).unlink()
        doc = document()
        doc["environment"]["dependencies"] = known([{"name": "descriptive", "reported_version": missing(),
            "records": known([ref("shallow-" + kind, "assessed_dependency", kind).to_dict() for kind in ("source", "work_product_manifest", "tool_release")]),
            "artifacts": known([]), "limitations": missing()}])
        for report, role in ((doc["execution_permission"], "reported_permission_decision"),
                             *((doc["qualification"][name], "reported_qualification_decision") for name in DIMENSIONS),
                             (doc["lifecycle"], "reported_lifecycle_decision")):
            report["decisions"] = known([ref("shallow-decision", role, "decision").to_dict()])
            supplied = evidence("execution", "reported_tool_execution")
            supplied["records"] = known([ref("shallow-tool_execution", "reported_tool_execution", "tool_execution").to_dict()])
            supplied["artifacts"] = known([])
            report["evidence"] = known([supplied])
        self.store.submit_typed(request("passive-shallow", [assessment(doc)]))

    def test_release_reported_qualification_cycle_remains_shallow(self):
        """A release may describe this assessment without constraining its generic qualification payload."""
        from tests.tool_release_fixtures import RECORD_SLOTS
        release = declaration(links=[(RECORD_SLOTS[3], ref("assessment", "reported_qualification", "tool_assessment"))])
        doc = document(release=release)
        self.store.submit_typed(request("cycle", [assessment(doc), tool(release)]))
        # A different release can report a completely generic assessment shallowly.
        self.store.submit(request("generic", [record("generic-assessment", kind="tool_assessment")]))
        release = declaration("reporter", links=[(RECORD_SLOTS[3], ref("generic-assessment", "reported_qualification", "tool_assessment"))])
        self.store.submit_typed(request("reporter", [tool(release)]))

    def test_known_empty_unknown_unavailable_and_denied_reports_are_retained(self):
        """No missing facts or reported denials are filled from other dimensions or creator provenance."""
        self.seed_release()
        for state in ("known", "unknown", "unavailable"):
            doc = document(state)
            doc["checks"] = known([]) if state == "known" else missing(state)
            doc["environment"]["dependencies"] = known([]) if state == "known" else missing(state)
            doc["execution_permission"]["status"] = "denied"
            doc["qualification"]["scientific_applicability"]["outcome"] = "inconclusive"
            self.store.submit_typed(request(state, [assessment(doc)]))
            self.assertEqual(self.store.get_typed_revision(state, 1)[1].to_dict(), doc)

    def test_cached_release_pairing_is_checked_for_each_owner_and_history(self):
        """A good incoming pairing cannot hide a mismatched owner's same exact cached release."""
        release = self.seed_release()
        for reverse in (False, True):
            good = document("good-" + str(reverse))
            bad = document("bad-" + str(reverse))
            bad["target"]["release_id"] = "sha256:" + "0" * 64
            batch = [assessment(good), assessment(bad)]
            error = self.rejects(request("owners-" + str(reverse), list(reversed(batch)) if reverse else batch))
            self.assertIn(bad["assessment_id"], str(error))
        # Two consumers share a historical prefix; the oldest mismatch remains visible.
        old = document("historical")
        old["target"]["release_id"] = "sha256:" + "0" * 64
        self.store.submit(request("historical-1", [assessment(old)]))
        for revision in (2, 3):
            self.store.submit(request("historical-" + str(revision), [assessment(document("historical"), revision)], {"historical": revision - 1}))
        consumers = []
        for name in ("left", "right"):
            doc = document(name)
            doc["lifecycle"]["supersedes"] = known([ref("historical", "supersedes_assessment", "tool_assessment", 3).to_dict()])
            consumers.append(assessment(doc))
        error = self.rejects(request("shared-prefix", consumers))
        self.assertIn("historical@1", str(error))

    def test_all_lifecycle_pins_forward_and_missing_wrong_kind(self):
        """Replacement, supersedes and superseded_by keep their exact ordered constrained roles."""
        release = self.seed_release()
        replacement = self.seed_release(declaration("replacement"))
        doc = document()
        doc["lifecycle"]["replacement"] = known({"release": ref("replacement", "replacement_release", "tool_release").to_dict(), "release_id": replacement.release_id})
        doc["lifecycle"]["supersedes"] = known([ref("earlier", "supersedes_assessment", "tool_assessment").to_dict()])
        doc["lifecycle"]["superseded_by"] = known(ref("later", "superseded_by_assessment", "tool_assessment").to_dict())
        self.store.submit_typed(request("lifecycle", [assessment(doc), assessment(document("earlier")), assessment(document("later"))]))
        self.assertEqual([item.relationship for item in self.store.get_revision("assessment", 1).record_references],
                         ["assessed_release", "replacement_release", "supersedes_assessment", "superseded_by_assessment"])
        for role in ("replacement_release", "supersedes_assessment", "superseded_by_assessment"):
            for wrong_kind in (False, True):
                bad = deepcopy(doc)
                bad["assessment_id"] = role + "-" + str(wrong_kind)
                target_name = "target-" + bad["assessment_id"]
                entry = (bad["lifecycle"]["replacement"]["value"]["release"] if role == "replacement_release" else
                         bad["lifecycle"]["supersedes"]["value"][0] if role == "supersedes_assessment" else
                         bad["lifecycle"]["superseded_by"]["value"])
                entry["record_id"] = target_name
                if wrong_kind:
                    self.store.submit(request(target_name, [record(target_name)]))
                self.rejects(request(bad["assessment_id"], [assessment(bad)]))

    def test_reported_review_reuses_route_conclusion_validation(self):
        """Assessment reachability requires real Review closure and exact candidate membership in routes."""
        from dataclasses import replace
        from tests.test_assessment_store import mixed_graph, declarations
        from tests.test_typed_store import envelope, claim
        from tests.tool_assessment_fixtures import wire
        release = self.seed_release(declaration("assessed_tool"))
        artifact = self.store.put_artifact(b"scientific report artifact")
        graph = mixed_graph(artifact)
        route = _decode_typed_envelope(graph[2])
        graph[2] = envelope("route", replace(route, conclusions=[ref("other-candidate", "conclusion", "claim")]))
        self.store.submit(request("generic-scientific-graph", [*graph, *declarations(), envelope("other-candidate", claim())]))
        doc = document(release=release)
        entry = wire()["reviews"]["value"][0]
        entry["review"] = ref("review-a", "reported_review", "review").to_dict()
        entry["evidence"] = known([])
        doc["reviews"] = known([entry])
        error = self.rejects(request("bad-route", [assessment(doc)]))
        self.assertIn("review-a@1", str(error))
        self.assertIn("route@1", str(error))
        self.assertIn("candidate@1", str(error))
