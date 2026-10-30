"""Durable synthetic assessments: exact admission, retained disagreement and real recovery."""

from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError, ArtifactStore
from research_pipeline.assessment import (
    IndependenceDeclaration, Issue, Review, SubstantiveAssessment, SupportRouteAssessment,
    decode_envelope as decode_assessment, encode_envelope as encode_assessment,
)
from research_pipeline.backup import create_backup, inspect_backup, restore_backup
from research_pipeline.domain import (
    CreationProvenance, DomainValidationError, RecordEnvelope, Submission, SubmissionReceipt,
)
from research_pipeline.scientific import (
    Evidence, Justification, NotTypedContentError, decode_envelope as decode_scientific,
)
from research_pipeline.store import (
    RecordNotFoundError, RecordStore, ReferenceResolutionError, RevisionConflictError,
    StoreClosedError, SubmissionConflictError,
)
from tests.legacy import create_legacy, historical_store, table_values
from tests.test_store import CONTROLLER, CREATOR, record, request
from tests.test_typed_store import claim, context, envelope, ref


TEXT = "  Synthetic ∀ x ∈ ℝ: scope ε → 0; 𝒜 remains conditional\n  "
REVIEWER_B = CreationProvenance("reviewer-b", "2026-10-30T12:30:00Z", {"source": "synthetic"})


def review():
    """Declare conditional favorable scope, mixed checks and two separately judged routes."""
    independence = IndependenceDeclaration("answer_blind_reconstruction", "candidate_aware_audit",
                                          [], [], [], ["declared method"], [], [], ["Unverified exposure"])
    assessment = SubstantiveAssessment("under_review", "supported_within_scope", ["analytical", "heuristic"],
                                       "requires_reassessment", "unassessed", TEXT, ["If premises hold"],
                                       ["Existence remains open"], [])
    routes = [SupportRouteAssessment(ref("route", "assessed_route", "justification"), "sufficient",
                                    TEXT, ["Verify all premises"], []),
              SupportRouteAssessment(ref("alternative", "assessed_route", "justification"), "invalid",
                                     "Invalid support does not refute candidate", [], ["Synthetic only"])]
    return Review(ref("candidate", "candidate_claim", "claim"),
                  ref("target-context", "target_context", "research_context"), "Reviewer α", independence,
                  ref("manifest", "context_manifest", "work_product_manifest"),
                  ref("policy", "authorization_policy", "decision"),
                  [ref("evidence", "reported_evidence", "evidence"),
                   ref("tool", "reported_tool_execution", "tool_execution")],
                  assessment, routes, ["Compare assumptions"], [], [], "synthetic")


def issue():
    """Declare an objection with forward/self generic targets and constrained supporting evidence."""
    return Issue(TEXT, [ref("review-b", "affected_record", "review"),
                        ref("issue-peer", "affected_record", "issue"),
                        ref("issue", "affected_record", "issue")],
                 "The declared conditions remain unverified", "blocking", "Compare declared premises",
                 "open", TEXT, [], [ref("evidence", "supporting_evidence", "evidence")], [], "unverified")


def assessment_envelope(identity, value, revision=1, provenance=CREATOR):
    """Encode assessment content with explicit record attribution and exact projected links."""
    return encode_assessment(identity, revision, value, provenance)


def decoded(item):
    """Decode known fixture kinds independently through their public codec contracts."""
    return (decode_assessment if item.kind in ("review", "issue") else decode_scientific)(item)


def declarations():
    """Seed generic manifest, policy, reported execution and completed task separately."""
    return [record("manifest", kind="work_product_manifest"), record("policy", kind="decision"),
            record("tool", kind="tool_execution"), record("task", kind="task_specification")]


def mixed_graph(artifact):
    """Build all six typed kinds in forward order, with distinct candidate/route/target contexts."""
    route = Justification(ref("route-context", "context", "research_context"),
                          [ref("candidate", "premise", "claim")], [], "Synthetic route α",
                          [ref("candidate", "conclusion", "claim")],
                          [ref("evidence", "evidence", "evidence")], [])
    evidence = Evidence([artifact], ref("context", "context", "research_context"), "synthetic property",
                        [ref("candidate", "target_claim", "claim")], "declared method",
                        [ref("task", "input_record", None), ref("evidence", "input_record", "evidence")],
                        [], [], TEXT, [], [], "synthetic")
    first = review()
    second = replace(first, reviewer="Reviewer β", assessment=replace(first.assessment,
                     scientific_disposition="disputed", applicability="unresolved"),
                     route_assessments=[replace(r, outcome="invalid") for r in first.route_assessments])
    peer = replace(issue(), affected_records=[ref("issue", "affected_record", "issue")], supporting_evidence=[])
    return [assessment_envelope("issue", issue()), assessment_envelope("review-a", first),
            envelope("route", route), assessment_envelope("review-b", second, provenance=REVIEWER_B),
            assessment_envelope("issue-peer", peer), envelope("candidate", claim()),
            envelope("alternative", replace(route, method="Separate route β", premises=(), evidence=())),
            envelope("evidence", evidence), envelope("context", context()),
            envelope("route-context", replace(context(), question="Route's separate scope")),
            envelope("target-context", replace(context(), question="Review's separate scope"))]


def metadata(root):
    """Snapshot every application table, including migration history when schema 2 is present."""
    connection = sqlite3.connect((Path(root) / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True)
    try:
        tables = ("identities", "revisions", "record_links", "artifacts", "artifact_links",
                  "submissions", "audit_events")
        if connection.execute("PRAGMA user_version").fetchone()[0] == 2:
            tables += ("migration_history",)
        return {name: connection.execute(f"SELECT * FROM {name} ORDER BY 1,2").fetchall() for name in tables}
    finally:
        connection.close()


class AssessmentStoreTests(unittest.TestCase):
    """Assert observable SQLite outcomes using real outside-source stores and bounded children."""

    def setUp(self):
        """Create a private runtime outside source and register handle cleanup before directory removal."""
        temporary = TemporaryDirectory(dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "assessments #? ü"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)

    def child(self, program, *arguments, expected=0):
        """Execute fresh candidate-source Python with a bounded timeout and explicit exit assertions."""
        source = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, arguments)],
                                cwd=self.parent, env={**os.environ, "PYTHONPATH": str(source),
                                                     "PYTHONDONTWRITEBYTECODE": "1"},
                                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def populate(self):
        """Commit generic declarations separately, then return the mixed typed request and receipt."""
        self.store.submit(request("declarations", declarations()))
        artifact = self.store.put_artifact(b"synthetic observation; no scientific execution")
        batch = request("mixed", mixed_graph(artifact))
        return artifact, batch, self.store.submit_typed(batch)

    def rejects(self, batch, error=ReferenceResolutionError, store=None):
        """Require a failure to leave every table, head, event and receipt exactly unchanged."""
        store = self.store if store is None else store
        before = metadata(self.root)
        with self.assertRaises(error) as caught:
            store.submit_typed(batch)
        self.assertEqual(metadata(self.root), before)
        return caught.exception

    def rejected_value(self, value, error=ReferenceResolutionError):
        """Place a valid early member ahead of a failing assessment to prove all-or-nothing admission."""
        return self.rejects(request("rejected", [envelope("early", context()),
                                                assessment_envelope("rejected", value)]), error)

    def test_mixed_forward_graph_revisions_reopen_and_fresh_process(self):
        """Retain complete disagreement, exact contexts and provenance across append and process restart."""
        _, initial, receipt = self.populate()
        original_claim = self.store.history("candidate")
        for item in initial.records:
            self.assertEqual(self.store.get_typed_revision(item.record_id, 1), (item, decoded(item)))
            self.assertEqual(decoded(item).to_dict(), item.content)
        self.assertEqual(receipt.revisions, tuple((r.record_id, 1) for r in initial.records))
        self.assertEqual(receipt.provenance, CONTROLLER)
        first, second = (self.store.get_typed_revision(name, 1)[1] for name in ("review-a", "review-b"))
        self.assertEqual((first.route_assessments[0].outcome, second.route_assessments[0].outcome),
                         ("sufficient", "invalid"))
        self.assertEqual(first.assessment.obligations, ("Existence remains open",))
        self.assertEqual(first.independence.shared_sources, ())
        self.assertEqual([r.relationship for r in first.reported_checks],
                         ["reported_evidence", "reported_tool_execution"])
        advanced = envelope("target-context", replace(context(), question="New target context"), 2)
        self.store.submit_typed(request("advance-context", [advanced], {"target-context": 1}))
        inapplicable = replace(first, assessment=replace(first.assessment, applicability="inapplicable"),
                              route_assessments=[replace(r, outcome="inapplicable") for r in first.route_assessments])
        changed_review = assessment_envelope("review-a", inapplicable, 2)
        review_receipt = self.store.submit_typed(request("review-revision", [changed_review], {"review-a": 1}))
        changed_issue = assessment_envelope("issue", replace(issue(), disposition="under_investigation"), 2)
        issue_receipt = self.store.submit_typed(request("issue-revision", [changed_issue], {"issue": 1}))
        direct = assessment_envelope("direct", replace(first, route_assessments=[], reported_checks=[]))
        self.store.submit_typed(request("direct", [direct]))
        self.assertEqual(self.store.history("candidate"), original_claim)
        self.assertEqual(original_claim[0].scientific_disposition, "provisional")
        self.assertEqual(self.store.get_typed_revision("review-a", 2)[1].target_context.revision, 1)
        self.assertEqual(self.store.get_typed_revision("direct", 1)[1].route_assessments, ())
        expected_ids = {r.record_id for r in initial.records} | {r.record_id for r in declarations()} | {"direct"}
        self.assertEqual({r[0] for r in metadata(self.root)["identities"]}, expected_ids)
        events = [event.to_dict() for event in self.store.audit_events()]
        self.store.close()
        self.store = RecordStore.open(self.root)
        self.addCleanup(self.store.close)
        retained = (*initial.records, advanced, changed_review, changed_issue, direct)
        for item in retained:
            exposed, value = self.store.get_typed_revision(item.record_id, item.revision)
            self.assertEqual((exposed, value), (item, decoded(item)))
            exposed.content.clear()
            value.to_dict().clear()
            self.assertEqual(self.store.get_typed_revision(item.record_id, item.revision), (item, decoded(item)))
        self.assertEqual(self.store.history("review-a"), (initial.records[1], changed_review))
        self.assertEqual(self.store.history("issue"), (initial.records[0], changed_issue))
        self.assertEqual(self.store.get_submission("review-revision"), review_receipt)
        self.assertEqual(self.store.get_submission("issue-revision"), issue_receipt)
        pairs = [[r.record_id, r.revision] for r in retained]
        output = self.child('''
import json, sys
from research_pipeline.store import RecordStore
from research_pipeline.domain import Submission
with RecordStore.open(sys.argv[1]) as store:
    print(json.dumps({"values": [[e.to_dict(), v.to_dict()] for key in json.loads(sys.argv[2])
                                  for e, v in [store.get_typed_revision(*key)]],
                      "receipt": store.submit_typed(Submission.from_dict(json.loads(sys.argv[3]))).to_dict(),
                      "revision_receipts": [store.get_submission(name).to_dict()
                                            for name in ("review-revision", "issue-revision")],
                      "events": [e.to_dict() for e in store.audit_events()]}))
''', self.root, json.dumps(pairs), json.dumps(initial.to_dict()))
        self.assertEqual(json.loads(output), {"values": [[r.to_dict(), decoded(r).to_dict()] for r in retained],
                                              "receipt": receipt.to_dict(),
                                              "revision_receipts": [review_receipt.to_dict(), issue_receipt.to_dict()],
                                              "events": events})

    def test_route_membership_for_batch_history_outcomes_and_exact_revision(self):
        """All route outcomes require the exact candidate, for proposed and historical justifications."""
        self.populate()
        self.store.submit_typed(request("other-candidate", [envelope("other-candidate", claim()),
                                                        envelope("candidate", claim(), 2)], {"other-candidate": 0, "candidate": 1}))
        original = self.store.get_typed_revision("route", 1)[1]
        for candidate, revision in (("other-candidate", 1), ("candidate", 2)):
            wrong = replace(original, conclusions=[ref(candidate, "conclusion", "claim", revision)])
            route_id = f"wrong-{candidate}-{revision}"
            route_record = envelope(route_id, wrong)
            for outcome in ("sufficient", "invalid", "stale", "inapplicable", "incomplete", "unresolved"):
                value = replace(review(), route_assessments=[SupportRouteAssessment(
                    ref(route_id, "assessed_route", "justification"), outcome, "Synthetic judgment", [], [])])
                bad = request("wrong-proposed", [envelope("early", context()), assessment_envelope("bad", value), route_record])
                error = self.rejects(bad)
                self.assertIn("candidate@1", str(error))
                self.assertIn(route_id + "@1", str(error))
                self.assertIn("bad@1", str(error))
            self.store.submit_typed(request(route_id, [route_record]))
            self.rejected_value(value)
        multi = envelope("multi", replace(original, conclusions=[ref("other-candidate", "conclusion", "claim"),
                                                                 ref("candidate", "conclusion", "claim")]))
        valid = replace(review(), route_assessments=[replace(review().route_assessments[0],
                                                             justification=ref("multi", "assessed_route", "justification"))])
        self.store.submit_typed(request("multi", [assessment_envelope("multi-review", valid), multi]))
        self.assertEqual(self.store.get_typed_revision("multi-review", 1)[1], valid)
        # A cached route still has a separate membership obligation for each reviewer.
        other = replace(review(), candidate_claim=ref("other-candidate", "candidate_claim", "claim"))
        for members in ((review(), other), (other, review())):
            self.rejects(request("shared-cache", [assessment_envelope("a", members[0]),
                                                   assessment_envelope("b", members[1])]))

    def test_missing_and_wrong_kind_assessment_roles_are_atomic(self):
        """Every constrained and generic assessment role requires exact existence and declared kind."""
        self.populate()
        base = review()
        for identity in ("absent", "task"):
            for field in ("candidate_claim", "target_context", "context_manifest", "authorization_policy"):
                with self.subTest(field=field, target=identity):
                    value = replace(base, **{field: replace(getattr(base, field), record_id=identity)})
                    error = self.rejected_value(value)
                    self.assertIn(field, str(error))
                    self.assertIn(identity + "@1", str(error))
            for role, kind in (("reported_evidence", "evidence"), ("reported_tool_execution", "tool_execution")):
                self.rejected_value(replace(base, reported_checks=[ref(identity, role, kind)]))
            self.rejected_value(replace(base, route_assessments=[replace(base.route_assessments[0],
                                justification=ref(identity, "assessed_route", "justification"))]))
            self.rejected_value(replace(issue(), supporting_evidence=[ref(identity, "supporting_evidence", "evidence")]))
            self.rejected_value(replace(issue(), affected_records=[ref(identity, "affected_record", "claim")]))
        self.rejected_value(replace(base, candidate_claim=replace(base.candidate_claim, revision=99)))

    def test_historical_constrained_content_and_deeper_closure_fail_atomically(self):
        """Historical codec errors and deeper scientific failures retain role/target diagnostics and causes."""
        self.populate()
        bases = {"candidate": self.store.get_revision("candidate", 1),
                 "route": self.store.get_revision("route", 1),
                 "evidence": self.store.get_revision("evidence", 1),
                 "target-context": self.store.get_revision("target-context", 1)}
        for key, base in bases.items():
            for variant in ("untyped", "version", "format", "malformed", "links"):
                document = base.to_dict()
                identity = f"{key}-{variant}"
                document["record_id"] = identity
                if variant == "untyped":
                    del document["content"]["format"]
                elif variant == "version":
                    document["content"]["version"] = 99
                elif variant == "format":
                    document["content"]["format"] = ["unknown"]
                elif variant == "malformed":
                    document["content"]["extra"] = True
                else:
                    document["record_references"] = [] if base.record_references else [ref("task", "unwanted", None).to_dict()]
                self.store.submit(request(identity, [RecordEnvelope.from_dict(document)]))
                value = review()
                if key == "candidate":
                    value = replace(value, candidate_claim=ref(identity, "candidate_claim", "claim"))
                elif key == "route":
                    value = replace(value, route_assessments=[replace(value.route_assessments[0],
                                    justification=ref(identity, "assessed_route", "justification"))])
                elif key == "evidence":
                    value = replace(value, reported_checks=[ref(identity, "reported_evidence", "evidence")])
                else:
                    value = replace(value, target_context=ref(identity, "target_context", "research_context"))
                with self.subTest(kind=key, variant=variant):
                    error = self.rejected_value(value)
                    self.assertIn(identity + "@1", str(error))
                    self.assertIsInstance(error.__cause__, DomainValidationError)
                    if variant == "untyped":
                        self.assertIsInstance(error.__cause__, NotTypedContentError)
        self.store.submit(request("raw-scope", [record("raw-scope")]))
        # These envelopes are locally coherent; only traversal reveals their raw context.
        bad_claim = envelope("deep-candidate", claim("raw-scope"))
        bad_route = envelope("deep-route", replace(decoded(bases["route"]), context=ref("raw-scope", "context", "research_context")))
        bad_evidence = envelope("deep-evidence", replace(decoded(bases["evidence"]), context=ref("raw-scope", "context", "research_context")))
        self.store.submit(request("deep", [bad_claim, bad_route, bad_evidence]))
        values = [replace(review(), candidate_claim=ref("deep-candidate", "candidate_claim", "claim")),
                  replace(review(), route_assessments=[replace(review().route_assessments[0], justification=ref("deep-route", "assessed_route", "justification"))]),
                  replace(review(), reported_checks=[ref("deep-evidence", "reported_evidence", "evidence")]),
                  replace(issue(), supporting_evidence=[ref("deep-evidence", "supporting_evidence", "evidence")])]
        for value in values:
            error = self.rejected_value(value)
            self.assertIn("context target raw-scope@1", str(error))
            self.assertIsInstance(error.__cause__, NotTypedContentError)

    def test_generic_roles_preserve_unsupported_payloads_without_traversal(self):
        """Generic declarations may name any kind, with opaque payloads, outgoing links and lost bytes."""
        self.populate()
        artifact = self.store.put_artifact(b"generic bytes intentionally unavailable later")
        kinds = ("research_context", "claim", "justification", "evidence", "task_specification",
                 "project", "run", "corpus_manifest", "branch", "source", "work_product_manifest",
                 "tool_release", "tool_assessment", "issue", "review", "promotion_eligibility",
                 "decision", "attempt", "tool_execution", "event")
        targets = [record("generic-" + kind, kind=kind,
                          content={"format": "research_pipeline.assessment_content", "version": 99,
                                   "kind": kind, "opaque": ["not interpreted"]},
                          record_references=[ref("generic-" + kind, "self", kind)],
                          artifact_references=[artifact]) for kind in kinds]
        self.store.submit(request("generic-targets", targets))
        (self.root / "objects" / artifact.digest).unlink()
        affected = [ref(item.record_id, "affected_record", item.kind) for item in targets]
        value = replace(issue(), affected_records=affected, supporting_evidence=[])
        generic_review = replace(review(), context_manifest=ref("generic-work_product_manifest", "context_manifest", "work_product_manifest"),
                                 authorization_policy=ref("generic-decision", "authorization_policy", "decision"),
                                 reported_checks=[ref("generic-tool_execution", "reported_tool_execution", "tool_execution")])
        original = RecordStore._metadata_envelope

        def constrained_only(store, connection, identity, revision):
            """Fail if admission reconstructs a generic target instead of checking just its key/kind."""
            self.assertFalse(identity.startswith("generic-"), identity)
            return original(store, connection, identity, revision)

        with patch.object(RecordStore, "_metadata_envelope", constrained_only):
            self.store.submit_typed(request("generic-roles", [assessment_envelope("consumer-issue", value),
                                                             assessment_envelope("consumer-review", generic_review)]))
        self.assertEqual(self.store.get_typed_revision("consumer-issue", 1)[1], value)
        # A shallow occurrence cannot confer typing when the same key is used as Evidence.
        for supporting in (True, False):
            bad = replace(value, supporting_evidence=[ref("generic-evidence", "supporting_evidence", "evidence")])
            members = [assessment_envelope("both", bad)] if supporting else [
                assessment_envelope("generic-only", value), assessment_envelope("constrained", replace(review(),
                    reported_checks=[ref("generic-evidence", "reported_evidence", "evidence")]))]
            error = self.rejects(request("generic-does-not-certify", members))
            self.assertIn("generic-evidence@1", str(error))
            self.assertIsInstance(error.__cause__, DomainValidationError)
        # Every proposed member is decoded, even if only an affected_record points to it.
        invalid = record("forward", kind="review", content={"format": "research_pipeline.assessment_content", "version": 99})
        self.rejects(request("bad-forward", [assessment_envelope("forward-issue", replace(value,
                     affected_records=[ref("forward", "affected_record", "review")])), invalid]), DomainValidationError)

    def test_historical_evidence_generic_inputs_stay_shallow(self):
        """Outgoing inputs of reached Evidence require keys/kinds without reading generic targets or bytes."""
        artifact, _, _ = self.populate()
        opaque = record("opaque", kind="claim", content={"format": "unknown", "version": 77})
        self.store.submit(request("opaque", [opaque]))
        evidence = replace(self.store.get_typed_revision("evidence", 1)[1],
                           input_records=[ref("opaque", "input_record", None)])
        self.store.submit_typed(request("historical-evidence", [envelope("historical-evidence", evidence)]))
        (self.root / "objects" / artifact.digest).unlink()
        for name, value in (("review", replace(review(), reported_checks=[ref("historical-evidence", "reported_evidence", "evidence")])),
                            ("issue", replace(issue(), supporting_evidence=[ref("historical-evidence", "supporting_evidence", "evidence")]))):
            self.store.submit_typed(request("after-loss-" + name, [assessment_envelope("after-loss-" + name, value)]))
            self.assertEqual(self.store.get_typed_revision("after-loss-" + name, 1)[1], value)
        with self.assertRaises(ArtifactNotFoundError):
            self.store.get_typed_revision("historical-evidence", 1)
        # Supported generic persistence preserves incoherent typed-looking content;
        # an exact typed read remains local and never retrospectively admits its graph.
        invalid_membership = replace(review(), candidate_claim=ref("opaque", "candidate_claim", "claim"))
        self.store.submit(request("raw-review", [assessment_envelope("raw-review", invalid_membership)]))
        self.assertEqual(self.store.get_typed_revision("raw-review", 1)[1], invalid_membership)

    def test_submitted_discriminators_and_ordered_links_are_validated_locally(self):
        """Malformed content, format dispatch and every link projection fail before any metadata changes."""
        self.populate()
        a, b = self.store.put_artifact(b"attachment a"), self.store.put_artifact(b"attachment b")
        for value in (replace(review(), artifacts=[a, b]), replace(issue(), artifacts=[a, b])):
            original = assessment_envelope("bad", value)
            variants = []
            for field in ("record_references", "artifact_references"):
                links = original.to_dict()[field]
                substitute = dict(links[0])
                substitute["record_id" if field == "record_references" else "digest"] = "task" if field == "record_references" else "a" * 64
                for changed in (links[1:], [substitute, *links[1:]], list(reversed(links)), [*links, links[0]]):
                    document = original.to_dict()
                    document[field] = changed
                    variants.append((document, DomainValidationError))
            for key, values in (("format", (None, [], "unknown", "research_pipeline.scientific_content")),
                                ("version", (True, "1", 99)), ("kind", ("claim", "unknown"))):
                for invalid in values:
                    document = original.to_dict()
                    document["content"][key] = invalid
                    variants.append((document, DomainValidationError))
            document = original.to_dict()
            del document["content"]["format"]
            variants.append((document, NotTypedContentError))
            document = original.to_dict()
            del document["content"]["origin"]
            variants.append((document, DomainValidationError))
            for document, error in variants:
                with self.subTest(kind=original.kind, content=document["content"].get("format"), error=error):
                    self.rejects(request("malformed", [envelope("early", context()), RecordEnvelope.from_dict(document)]), error)
        for generic in declarations():
            self.rejects(request("generic-member", [envelope("early", context()), generic]), NotTypedContentError)

    def test_direct_artifact_damage_rejects_both_kinds_and_exact_reads(self):
        """Missing and corrupt direct assessment attachments fail writes atomically and exact reads."""
        self.populate()
        for kind, value in (("review", review()), ("issue", issue())):
            artifact = self.store.put_artifact(("direct " + kind).encode())
            attached = replace(value, artifacts=[artifact])
            identity = "attached-" + kind
            self.store.submit_typed(request(identity, [assessment_envelope(identity, attached)]))
            path = self.root / "objects" / artifact.digest
            for damage, error in (("corrupt", ArtifactIntegrityError), ("missing", ArtifactNotFoundError)):
                if damage == "corrupt":
                    path.chmod(0o600)
                    path.write_bytes(b"corrupt content")
                    path.chmod(0o400)
                else:
                    path.unlink()
                self.rejected_value(attached, error)
                with self.assertRaises(error):
                    self.store.get_typed_revision(identity, 1)
        with self.assertRaises(RecordNotFoundError):
            self.store.get_typed_revision("review-a", 99)
        self.store.close()
        with self.assertRaises(StoreClosedError):
            self.store.get_typed_revision("review-a", 1)
        with self.assertRaises(StoreClosedError):
            self.store.submit_typed(request("closed", [assessment_envelope("closed", review())]))

    def test_retry_bypasses_admission_heads_and_bytes_but_not_local_decoding(self):
        """Original receipts survive revisions/damage; canonical changes conflict and malformed retries fail."""
        artifact, _, _ = self.populate()
        first = assessment_envelope("attached-review", replace(review(), artifacts=[artifact]))
        second = assessment_envelope("attached-issue", replace(issue(), artifacts=[artifact]))
        initial = request("assessment-retry", [first, second])
        receipt = self.store.submit_typed(initial)
        self.store.submit_typed(request("assessment-next", [assessment_envelope("attached-review", review(), 2),
                                                             assessment_envelope("attached-issue", issue(), 2)],
                                        {"attached-review": 1, "attached-issue": 1}))
        reordered = initial.to_dict()
        reordered["expected_heads"] = dict(reversed(list(reordered["expected_heads"].items())))
        reordered["records"][0]["content"] = dict(reversed(list(reordered["records"][0]["content"].items())))
        reordered["records"][0]["content"]["assessment"] = dict(reversed(list(reordered["records"][0]["content"]["assessment"].items())))
        variants = []
        for change in ("content", "creator", "controller", "expectations", "members", "routes", "checks", "support-types"):
            document = initial.to_dict()
            if change == "content":
                document["records"][0] = assessment_envelope("attached-review", replace(decoded(first), reviewer="Other reviewer")).to_dict()
            elif change == "creator":
                document["records"][0]["provenance"]["actor"] = "other"
            elif change == "controller":
                document["provenance"]["actor"] = "other"
            elif change == "expectations":
                document["expected_heads"]["attached-review"] = 1
            elif change == "members":
                document["records"].reverse()
            else:
                original = decoded(first)
                field = {"routes": "route_assessments", "checks": "reported_checks", "support-types": "support_types"}[change]
                value = (replace(original, assessment=replace(original.assessment, support_types=tuple(reversed(original.assessment.support_types))))
                         if change == "support-types" else replace(original, **{field: tuple(reversed(getattr(original, field)))}))
                document["records"][0] = assessment_envelope("attached-review", value).to_dict()
            variants.append(Submission.from_dict(document))
        before = metadata(self.root)
        path = self.root / "objects" / artifact.digest
        for damage in ("corrupt", "missing"):
            if damage == "corrupt":
                path.chmod(0o600)
                path.write_bytes(b"corrupt")
                path.chmod(0o400)
            else:
                path.unlink()
            with patch.object(RecordStore, "_check_batch", side_effect=AssertionError("heads reached")), \
                    patch.object(RecordStore, "_check_typed_targets", side_effect=AssertionError("admission reached")), \
                    patch.object(RecordStore, "_metadata_envelope", side_effect=AssertionError("targets reached")), \
                    patch.object(ArtifactStore, "_verify_for_commit", side_effect=AssertionError("commit bytes reached")), \
                    patch.object(ArtifactStore, "verify", side_effect=AssertionError("read bytes reached")):
                self.assertEqual(self.store.submit_typed(Submission.from_dict(reordered)), receipt)
                for variant in variants:
                    with self.assertRaises(SubmissionConflictError):
                        self.store.submit_typed(variant)
                malformed = initial.to_dict()
                malformed["records"][0]["content"]["version"] = 99
                with self.assertRaises(DomainValidationError):
                    self.store.submit_typed(Submission.from_dict(malformed))
                malformed = initial.to_dict()
                malformed["records"][0]["record_references"].reverse()
                with self.assertRaises(DomainValidationError):
                    self.store.submit_typed(Submission.from_dict(malformed))
            self.assertEqual(metadata(self.root), before)
        self.assertEqual(len([e for e in self.store.audit_events() if e.submission_id == initial.submission_id]), 1)

    def test_generic_original_receipt_reconciles_without_route_certification(self):
        """A locally valid generic commit reconciles before membership; a new request must undergo admission."""
        self.populate()
        self.store.submit_typed(request("other", [envelope("other", claim())]))
        value = replace(review(), candidate_claim=ref("other", "candidate_claim", "claim"))
        initial = request("generic-assessment", [assessment_envelope("generic-assessment", value)])
        receipt = self.store.submit(initial)
        with patch.object(RecordStore, "_check_typed_targets", side_effect=AssertionError("admission reached")):
            self.assertEqual(self.store.submit_typed(initial), receipt)
        self.assertEqual(self.store.get_typed_revision("generic-assessment", 1)[1], value)
        error = self.rejected_value(value)
        self.assertIn("does not conclude candidate other@1", str(error))

    def test_independent_handles_compete_on_both_assessment_heads(self):
        """One append wins per expected head; stale requests are atomic and unrelated writes never rebind scope."""
        self.populate()
        candidate_history = self.store.history("candidate")
        with RecordStore.open(self.root) as other:
            for identity, value in (("review-a", review()), ("issue", issue())):
                sampled = other.head(identity)
                winner = assessment_envelope(identity, value, 2)
                self.store.submit_typed(request("winner-" + identity, [winner], {identity: sampled}))
                stale = request("stale-" + identity, [envelope("early", context()), winner], {"early": 0, identity: sampled})
                self.rejects(stale, RevisionConflictError, other)
                self.store.submit_typed(request("unrelated-" + identity, [envelope("unrelated-" + identity, context())]))
                next_record = assessment_envelope(identity, value, 3)
                other.submit_typed(request("next-" + identity, [next_record], {identity: 2}))
                self.assertEqual(self.store.head(identity), 3)
            self.store.submit_typed(request("new-scope", [envelope("target-context", context(), 2)], {"target-context": 1}))
            self.assertEqual(other.get_typed_revision("review-a", 3)[1].target_context.revision, 1)
        self.assertEqual(self.store.history("candidate"), candidate_history)

    def test_target_and_route_checks_hold_serialized_write_transaction(self):
        """A competing writer waits while both historical target decoding and membership run under BEGIN IMMEDIATE."""
        self.populate()
        inspecting, attempted, finished = threading.Event(), threading.Event(), threading.Event()
        failures = []
        original = RecordStore._check_typed_targets
        decoded_targets = []
        reconstruct = RecordStore._metadata_envelope

        def observe_target(store, connection, identity, revision):
            """Observe historical metadata reconstruction under the foreground's active write transaction."""
            self.assertTrue(connection.in_transaction)
            decoded_targets.append(identity)
            return reconstruct(store, connection, identity, revision)

        def inspect(store, connection, submission, values):
            """Hold the write lock through actual target and route checking while another handle attempts BEGIN."""
            if submission.submission_id != "foreground":
                return original(store, connection, submission, values)
            self.assertTrue(connection.in_transaction)
            inspecting.set()
            self.assertTrue(attempted.wait(5))
            self.assertFalse(finished.is_set())
            with patch.object(RecordStore, "_metadata_envelope", observe_target):
                original(store, connection, submission, values)
            self.assertFalse(finished.is_set())
            self.assertIn("route", decoded_targets)
            self.assertIn("candidate", decoded_targets)
            # Reject a different candidate through the same real admission helper,
            # proving membership is evaluated while this write transaction is held.
            invalid = replace(values[0], candidate_claim=ref("other", "candidate_claim", "claim"))
            with self.assertRaisesRegex(ReferenceResolutionError, "does not conclude candidate"):
                original(store, connection, request("probe", [assessment_envelope("probe", invalid)]), (invalid,))
            self.assertFalse(finished.is_set())

        def competitor():
            """Advance a route head with an independent handle while foreground admission owns the lock."""
            try:
                with RecordStore.open(self.root) as other:
                    self.assertTrue(inspecting.wait(5))
                    other._connection.set_trace_callback(lambda sql: attempted.set() if sql == "BEGIN IMMEDIATE" else None)
                    other.submit_typed(request("competitor", [envelope("route", original_route, 2)], {"route": 1}))
            except BaseException as error:
                failures.append(error)
            finally:
                finished.set()

        self.store.submit_typed(request("other", [envelope("other", claim())]))
        original_route = self.store.get_typed_revision("route", 1)[1]
        thread = threading.Thread(target=competitor)
        with patch.object(RecordStore, "_check_typed_targets", inspect):
            thread.start()
            try:
                self.store.submit_typed(request("foreground", [assessment_envelope("foreground", review())]))
            finally:
                inspecting.set()
                thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual([e.submission_id for e in self.store.audit_events()][-2:], ["foreground", "competitor"])
        self.assertEqual(self.store.get_typed_revision("foreground", 1)[1].route_assessments[0].justification.revision, 1)

    def test_abrupt_process_exit_rollback_and_original_request_reconciliation(self):
        """Real exits before metadata, mid-write and after COMMIT recover atomically in fresh processes."""
        self.populate()
        for index, boundary in enumerate(("before_metadata", "after_first_revision", "after_commit")):
            with self.subTest(boundary=boundary):
                identity = f"crash-{index}"
                # Force actual SQLite page spill and a hot rollback journal during
                # the first revision, rather than only killing buffered Python work.
                large = replace(review(), assessment=replace(review().assessment, rationale="x" * 3_000_000))
                batch = request(identity, [assessment_envelope(identity, large),
                                           envelope(identity + "-scope", context()),
                                           assessment_envelope(identity + "-issue", issue())])
                request_file = self.parent / (identity + ".json")
                request_file.write_text(json.dumps(batch.to_dict()), encoding="utf-8")
                before = metadata(self.root)
                snapshot_file = self.parent / (identity + "-before.json")
                snapshot_file.write_text(json.dumps(before), encoding="utf-8")
                prior_events = len(self.store.audit_events())
                self.child('''
import json, os, sys
from research_pipeline.domain import Submission
import research_pipeline.store as module
store = module.RecordStore.open(sys.argv[1])
def crash(point):
    """Exit at the real transaction seam without Python cleanup or a simulated commit."""
    if point == sys.argv[3]: os._exit(73)
module._fault = crash
with open(sys.argv[2], encoding="utf-8") as stream:
    store.submit_typed(Submission.from_dict(json.load(stream)))
raise AssertionError("fault boundary not reached")
''', self.root, request_file, boundary, expected=73)
                if boundary == "after_first_revision":
                    journal = self.root / "metadata.sqlite3-journal"
                    self.assertTrue(journal.exists())
                    self.assertGreater(journal.stat().st_size, 512)
                output = self.child('''
import json, sqlite3, sys
from pathlib import Path
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with open(sys.argv[2], encoding="utf-8") as stream:
    batch = Submission.from_dict(json.load(stream))
with open(sys.argv[4], encoding="utf-8") as stream:
    before = json.load(stream)
committed = sys.argv[3] == "after_commit"
with RecordStore.open(sys.argv[1]) as store:
    old = store.get_submission(batch.submission_id)
    assert (old is not None) == committed
    connection = sqlite3.connect((Path(sys.argv[1]) / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True)
    try:
        current = {name: [list(row) for row in connection.execute(f"SELECT * FROM {name} ORDER BY 1,2")]
                   for name in before}
    finally:
        connection.close()
    if not committed:
        assert current == before
    else:
        for name, rows in before.items():
            assert all(row in current[name] for row in rows), name
        assert len(current["revisions"]) == len(before["revisions"]) + len(batch.records)
        assert len(current["submissions"]) == len(before["submissions"]) + 1
        assert len(current["audit_events"]) == len(before["audit_events"]) + 1
        for item in batch.records:
            envelope, value = store.get_typed_revision(item.record_id, item.revision)
            assert envelope == item and value.to_dict() == item.content
    for item in batch.records:
        assert store.head(item.record_id) == (1 if committed else None)
    receipt = store.submit_typed(batch)
    if committed: assert receipt == old
    assert store.submit_typed(batch) == receipt
    assert len([e for e in store.audit_events() if e.submission_id == batch.submission_id]) == 1
    for item in batch.records:
        envelope, value = store.get_typed_revision(item.record_id, item.revision)
        assert envelope == item and value.to_dict() == item.content
    print(json.dumps(receipt.to_dict()))
''', self.root, request_file, boundary, snapshot_file)
                receipt = SubmissionReceipt.from_dict(json.loads(output))
                self.assertEqual(self.store.get_submission(identity), receipt)
                self.assertEqual(len(self.store.audit_events()), prior_events + 1)
                for item in batch.records:
                    self.assertEqual(self.store.get_typed_revision(item.record_id, 1), (item, decoded(item)))
                self.assertEqual(self.store.submit_typed(batch), receipt)

    def test_post_commit_exception_is_a_lost_acknowledgment(self):
        """An ordinary exception after real COMMIT preserves both assessments and their one original receipt."""
        self.populate()
        batch = request("lost-ack", [assessment_envelope("lost-review", review()),
                                     assessment_envelope("lost-issue", issue())])

        def lost_ack(boundary):
            """Raise only after the transaction has actually committed."""
            if boundary == "after_commit":
                raise RuntimeError("lost acknowledgment")

        with patch("research_pipeline.store._fault", lost_ack):
            with self.assertRaisesRegex(RuntimeError, "lost acknowledgment"):
                self.store.submit_typed(batch)
        self.store.close()
        self.store = RecordStore.open(self.root)
        self.addCleanup(self.store.close)
        receipt = self.store.get_submission("lost-ack")
        self.assertIsNotNone(receipt)
        self.assertEqual(self.store.submit_typed(batch), receipt)
        self.assertEqual([e.submission_id for e in self.store.audit_events()].count("lost-ack"), 1)
        for item in batch.records:
            self.assertEqual(self.store.get_typed_revision(item.record_id, 1)[0], item)

    def test_healthy_backup_exact_restore_and_retry_after_later_damage(self):
        """Backups retain all histories, canonical requests and unsupported assessment-looking generic data."""
        artifact, initial, receipt = self.populate()
        append = request("next", [assessment_envelope("review-a", replace(review(), reviewer="Updated assertion"), 2),
                                  assessment_envelope("issue", replace(issue(), disposition="resolved"), 2)],
                         {"review-a": 1, "issue": 1})
        self.store.submit_typed(append)
        future = []
        for name, value in (("future-review", review()), ("future-issue", issue())):
            document = assessment_envelope(name, value).to_dict()
            document["content"]["version"] = 99
            document["content"]["future"] = ["opaque"]
            future.append(RecordEnvelope.from_dict(document))
        self.store.submit(request("future", future))
        before = metadata(self.root)
        histories = {identity: self.store.history(identity) for identity, _, _ in before["identities"]}
        backup, restored_root = self.parent / "backup", self.parent / "restored"
        info = create_backup(self.store, backup)
        self.assertEqual(inspect_backup(backup), info)
        with restore_backup(backup, restored_root) as restored:
            self.assertEqual(metadata(restored_root), before)
            self.assertEqual(restored.audit_events(), self.store.audit_events())
            for identity, history in histories.items():
                self.assertEqual(restored.history(identity), history)
            for item in future:
                self.assertEqual(restored.get_revision(item.record_id, 1), item)
                with self.assertRaises(DomainValidationError):
                    restored.get_typed_revision(item.record_id, 1)
            self.assertEqual(restored.submit_typed(initial), receipt)
            self.assertEqual(restored.submit_typed(append), self.store.get_submission("next"))
        output = self.child('''
import json, sys
from research_pipeline.domain import Submission
from research_pipeline.store import RecordStore
with RecordStore.open(sys.argv[1]) as store:
    batch = Submission.from_dict(json.loads(sys.argv[2]))
    print(json.dumps({"values": [[e.to_dict(), v.to_dict()] for item in batch.records
                                  for e, v in [store.get_typed_revision(item.record_id, item.revision)]],
                      "receipt": store.submit_typed(batch).to_dict(),
                      "events": [e.to_dict() for e in store.audit_events()]}))
''', restored_root, json.dumps(initial.to_dict()))
        self.assertEqual(json.loads(output), {"values": [[item.to_dict(), decoded(item).to_dict()] for item in initial.records],
                                              "receipt": receipt.to_dict(),
                                              "events": [e.to_dict() for e in self.store.audit_events()]})
        (restored_root / "objects" / artifact.digest).unlink()
        with RecordStore.open(restored_root) as restored:
            self.assertEqual(restored.submit_typed(initial), receipt)
            with self.assertRaises(ArtifactNotFoundError):
                restored.get_typed_revision("evidence", 1)
            self.assertEqual(metadata(restored_root), before)
        self.assertEqual(inspect_backup(backup), info)
        self.assertEqual(self.store.read_artifact(artifact), b"synthetic observation; no scientific execution")

    def test_schema_one_rejects_assessments_before_targets_without_implicit_migration(self):
        """Valid assessment envelopes on v1 retain the migration-required contract even when targets are absent."""
        root = self.parent / "empty-legacy"
        with create_legacy(root) as legacy:
            before = metadata(root)
            for value in (review(), issue()):
                with self.assertRaisesRegex(DomainValidationError, "migration"):
                    legacy.submit_typed(request("assessment", [envelope("early", context()),
                                                              assessment_envelope("assessment", value)]))
                self.assertEqual(metadata(root), before)
            connection = sqlite3.connect((root / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True)
            try:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone(), (1,))
            finally:
                connection.close()

    def test_explicit_migration_preserves_legacy_receipts_and_continued_assessments(self):
        """Explicit v1-to-v2 restore preserves historical data, then supports assessments and exact continued backups."""
        legacy_root, backup_root = self.parent / "legacy", self.parent / "legacy-backup"
        legacy, requests, _ = historical_store(legacy_root)
        self.addCleanup(legacy.close)
        original = table_values(legacy_root)
        receipts = [legacy.get_submission(item.submission_id) for item in requests]
        for value in (review(), issue()):
            with self.assertRaisesRegex(DomainValidationError, "migration"):
                legacy.submit_typed(request("reject", [assessment_envelope("reject", value)]))
            self.assertEqual(table_values(legacy_root), original)
        create_backup(legacy, backup_root)
        migrated_root = self.parent / "migrated"
        migration = CreationProvenance("migration-operator", "2026-10-30T15:00:00Z", {"source": "synthetic"})
        with restore_backup(backup_root, migrated_root, target_schema=2, migration_provenance=migration) as migrated:
            self.assertEqual(table_values(migrated_root), original)
            history = metadata(migrated_root)["migration_history"]
            self.assertEqual(len(history), 1)
            for item, receipt in zip(requests, receipts):
                self.assertEqual(migrated.get_submission(item.submission_id), receipt)
                self.assertEqual(migrated.submit(item), receipt)
            migrated.submit(request("declarations", declarations()[:3]))
            first = replace(review(), candidate_claim=ref("claim-a", "candidate_claim", "claim"),
                            target_context=ref("context", "target_context", "research_context"))
            objection = replace(issue(), affected_records=[ref("migrated-review", "affected_record", "review"),
                                                           ref("task", "affected_record", "task_specification")])
            batch = request("continued", [assessment_envelope("migrated-issue", objection),
                                           assessment_envelope("migrated-review", first)])
            receipt = migrated.submit_typed(batch)
            self.assertEqual(migrated.history("claim-a"), legacy.history("claim-a"))
            self.assertEqual(metadata(migrated_root)["migration_history"], history)
            continued_backup = self.parent / "continued-backup"
            info = create_backup(migrated, continued_backup)
            self.assertEqual(inspect_backup(continued_backup), info)
            expected = metadata(migrated_root)
            with restore_backup(continued_backup, self.parent / "continued-restored") as restored:
                self.assertEqual(metadata(self.parent / "continued-restored"), expected)
                self.assertEqual(restored.submit_typed(batch), receipt)
                for old, old_receipt in zip(requests, receipts):
                    self.assertEqual(restored.submit(old), old_receipt)
                for identity, _, _ in expected["identities"]:
                    self.assertEqual(restored.history(identity), migrated.history(identity))

    def test_documented_assessment_persistence_example(self):
        """Execute the actual Markdown persistence block in a fresh candidate-source interpreter."""
        document = (Path(__file__).resolve().parents[2] / "docs" / "attributed-assessments.md").read_text()
        section = document.split("## Runnable synthetic persistence example\n", 1)[1]
        program = section.split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)
