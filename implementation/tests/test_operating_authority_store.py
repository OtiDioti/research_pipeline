"""Real-store authority, current readiness, immutable recovery and reduced permissions."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import operating_authority as a
from research_pipeline.artifacts import ArtifactStore
from research_pipeline.domain import RecordEnvelope
from research_pipeline.store import RecordStore, RevisionConflictError, SubmissionConflictError
from tests.operating_fixtures import TIME, END, KEY, LIMITS, REVOKER_KEY, policy, revoker_policy, scope, empty, short_note, decision, prepare, sign
from tests.test_store import CREATOR, request, record
from tests.test_project import declaration, readiness
from tests.test_typed_store import ref
from research_pipeline.project import encode_envelope as project_envelope
from tests.test_typed_store import envelope, context
from tests.test_assessment_store import metadata


class OperatingStoreTests(unittest.TestCase):
    """Use independent actual stores without inheriting or duplicating predecessor test suites."""

    def setUp(self):
        """Create disposable outside-source runtime with cleanup after store closure."""
        temporary = TemporaryDirectory(prefix="authority-tests-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)

    def commit(self, signed, trust=None, **updates):
        """Append with explicit disposable policy/time and independent operation bounds."""
        return self.store.commit_operating_decision(signed, policy=policy() if trust is None else trust,
                                                   evaluated_at=TIME, limits=LIMITS, **updates)

    def inspect(self, purpose="setup", *, trust=None, time=TIME):
        """Inspect internally selected current state with no caller-selected decision revision."""
        return self.store.inspect_operating_eligibility("synthetic", "project", purpose=purpose,
            policy=policy() if trust is None else trust, evaluated_at=time, limits=LIMITS).to_dict()

    def test_incomplete_setup_main_scope_and_exact_original_recovery(self):
        """Incomplete setup permits only bounded setup; recovery survives latest-state changes and absent trust."""
        empty(self.store)
        operating_scope = scope()
        binding = prepare(self.store, operating_scope)
        self.assertEqual(binding.to_dict()["dossier"]["brief"], a.absent())
        signed = sign(decision(binding, operating_scope))
        receipt = self.commit(signed)
        self.assertTrue(self.inspect()["eligible"])
        self.assertEqual(self.inspect("main_research")["status"], "scope_mismatch")
        with self.assertRaises(a.AuthorityReadinessError):
            self.commit(sign(decision(prepare(self.store, scope("main_research")), scope("main_research"),
                revision=2, previous=a.encode_envelope(signed), operation="bad-main")))
        reduction = sign(decision(binding, revision=2, previous=a.encode_envelope(signed), outcome="revoke", operation="revoke"))
        self.commit(reduction)
        self.assertEqual(self.inspect()["status"], "revoked")
        self.assertEqual(self.inspect(time="2027-11-02T12:00:00.000000Z")["status"], "revoked")
        self.assertEqual(self.store.commit_operating_decision(signed, policy=None, evaluated_at=None, limits=LIMITS), receipt)
        self.assertEqual(self.store.get_operating_operation("approve", limits=LIMITS), receipt)
        self.assertNotIn("eligible", receipt.to_dict())
        changed = signed.to_dict(); changed["decision"]["rationale"] = "Different saved intent"
        with self.assertRaises(SubmissionConflictError):
            self.commit(sign(a.OperatingDecision(changed["decision"])))

    def test_short_note_artifacts_stale_and_unrelated_events(self):
        """A real short note with authenticated judgments qualifies; artifact loss and watched changes fail closed."""
        value, source, records = short_note(self.store)
        operating_scope = scope("main_research", data=True)
        binding = prepare(self.store, operating_scope)
        signed = sign(decision(binding, operating_scope))
        self.commit(signed)
        result = self.inspect("main_research")
        self.assertEqual(result["status"], "eligible_main_research")
        self.assertEqual(len(result["verified_artifacts"]), 3)
        self.assertTrue(result["recheck_required"])
        before = {r.record_id: self.store.history(r.record_id) for r in records}
        self.store.submit(request("audit-only", [record("unrelated", kind="event")]))
        self.assertTrue(self.inspect("main_research")["eligible"])
        self.assertNotEqual(result["watermark"], self.inspect("main_research")["watermark"])
        for identity, history in before.items():
            self.assertEqual(self.store.history(identity), history)
        path = self.root / "objects" / source.originals[0].artifact.digest
        path.unlink()
        self.assertEqual(self.inspect("main_research")["status"], "artifact_unavailable")
        self.store.submit_typed(request("context-change", [envelope("context", context(), 2)], {"context": 1}))
        self.assertEqual(self.inspect("main_research")["status"], "stale")
        # Independently authorized revoker works after both artifact loss and withdrawal
        # of all verification material for the original approver.
        reduced = sign(decision(binding, revision=2, previous=a.encode_envelope(signed), outcome="revoke", operation="reduce",
            principal_id="revoker", key_id="revoker1"), REVOKER_KEY)
        with patch.object(ArtifactStore, "verify", side_effect=AssertionError("reduction read artifact")), \
                patch.object(ArtifactStore, "_verify_for_commit", side_effect=AssertionError("reduction synchronized artifact")):
            self.commit(reduced, revoker_policy())
        self.assertEqual(self.inspect("main_research", trust=revoker_policy())["status"], "revoked")
        history = self.store.inspect_operating_history("synthetic", "project", policy=revoker_policy(), limits=LIMITS).to_dict()
        self.assertEqual([item["signature_status"] for item in history["decisions"]], ["unavailable", "verified"])
        self.assertEqual(self.store.get_operating_operation("approve", limits=LIMITS).to_dict()["decision"]["revision"], 1)

    def test_generic_compatibility_authentication_and_typed_dispatch(self):
        """Generic storage is inert until independently verified; typed dispatch cannot install new authority."""
        empty(self.store)
        signed = sign(decision(prepare(self.store, scope()), scope()))
        batch = a.submission(signed)
        with self.assertRaisesRegex(a.DomainValidationError, "commit_operating_decision"):
            self.store.submit_typed(batch)
        for trust in (policy(key=b"X" * 32), policy(projects=[]), policy(capabilities=[]), a.OperatorPolicy("elsewhere", [])):
            with self.assertRaises(a.AuthorityAuthenticationError):
                self.commit(signed, trust)
        receipt = self.store.submit(batch)
        self.assertEqual(self.store.submit_typed(batch), receipt)
        self.assertTrue(self.inspect()["eligible"])
        no_trust = self.store.inspect_operating_eligibility("synthetic", "project", purpose="setup", policy=None, evaluated_at=TIME, limits=LIMITS)
        self.assertEqual(no_trust.to_dict()["status"], "missing_trust")
        self.assertEqual(self.inspect(trust=policy(capabilities=[]))["status"], "policy_denied")
        self.assertEqual(self.inspect(trust=policy(key=b"X" * 32))["status"], "unauthenticated")
        self.store.submit(request("opaque-next", [RecordEnvelope(batch.records[0].record_id, 2, "decision", {}, batch.provenance)],
                                  {batch.records[0].record_id: 1}))
        with self.assertRaises(a.AuthorityIntegrityError):
            self.inspect()

    def test_validity_cas_and_rollback_loss(self):
        """Validity endpoints, exact CAS, precommit rollback and postcommit acknowledgment loss retain original identity."""
        empty(self.store)
        signed = sign(decision(prepare(self.store, scope()), scope()))
        before = metadata(self.root)
        for boundary in ("before_metadata", "after_first_revision", "after_commit"):
            def fail(point):
                """Inject a failure at an existing real store transaction boundary."""
                if point == boundary:
                    raise RuntimeError("synthetic acknowledgment failure")
            with patch("research_pipeline.store._fault", fail), self.assertRaises(RuntimeError):
                self.commit(signed)
            if boundary != "after_commit":
                self.assertEqual(metadata(self.root), before)
                self.assertIsNone(self.store.get_operating_operation("approve", limits=LIMITS))
        self.assertEqual(self.commit(signed), self.store.get_operating_operation("approve", limits=LIMITS))
        self.assertEqual(self.inspect(time="2026-11-02T11:59:59.999999Z")["status"], "not_yet_valid")
        self.assertTrue(self.inspect(time="2026-11-03T11:59:59.999999Z")["eligible"])
        self.assertEqual(self.inspect(time=END)["status"], "expired")
        conflicting = sign(decision(prepare(self.store, scope()), scope(), operation="competing"))
        with self.assertRaises(RevisionConflictError):
            self.commit(conflicting)

    def test_independent_bounds_and_stored_corruption_preflight(self):
        """Actual malformed types/JSON fail before reconstruction; bounds never return truncated success."""
        empty(self.store)
        signed = sign(decision(prepare(self.store, scope()), scope()))
        self.commit(signed)
        for changes in ({"max_decisions": 1, "max_history_revisions": 0}, {"max_records": 1},
                        {"max_references": 0}, {"max_record_bytes": 1}, {"max_metadata_bytes": 1}, {"max_result_bytes": 1}):
            with self.subTest(changes=changes), self.assertRaises(a.AuthorityLimitError):
                self.store.inspect_operating_eligibility("synthetic", "project", purpose="setup", policy=policy(), evaluated_at=TIME,
                                                        limits=replace(LIMITS, **changes))
        connection = self.store._connection
        original = connection.execute("SELECT content_json FROM revisions WHERE record_id='project'").fetchone()[0]
        connection.execute("UPDATE revisions SET content_json=? WHERE record_id='project'", (b"not text",))
        with self.assertRaises(a.AuthorityIntegrityError):
            self.inspect()
        connection.execute("UPDATE revisions SET content_json=? WHERE record_id='project'", (original,))
        connection.execute("UPDATE record_links SET ordinal=100 WHERE record_id=? AND ordinal=0", (signed.to_dict()["decision"]["decision_id"],))
        with self.assertRaises(a.AuthorityIntegrityError):
            self.store.get_operating_operation("approve", limits=LIMITS)

    def reduction(self, signed, outcome, selected, operation):
        """Sign a successor with a separate reducer and an explicit historical evidence selection."""
        previous = a.encode_envelope(signed)
        value = decision(a.OperatingBinding(signed.to_dict()["decision"]["binding"]),
            revision=previous.revision + 1, previous=previous, outcome=outcome, operation=operation,
            principal_id="revoker", key_id="revoker1").to_dict()
        value["judgments"]["evidence_declarations"] = selected
        return sign(a.OperatingDecision(value), REVOKER_KEY)

    def test_reductions_reject_unknown_declarations_atomically(self):
        """Both authorized reductions reject nonexistent evidence in an empty historical setup without writes."""
        empty(self.store)
        signed = sign(decision(prepare(self.store, scope()), scope()))
        self.commit(signed)
        identity = signed.to_dict()["decision"]["decision_id"]
        before = metadata(self.root)
        history = self.store.history(identity)
        for outcome in ("deny", "revoke"):
            operation = "unknown-" + outcome
            with self.subTest(outcome=outcome), self.assertRaises(a.AuthorityReadinessError):
                self.commit(self.reduction(signed, outcome, ["nonexistent"], operation), revoker_policy())
            self.assertEqual(metadata(self.root), before)
            self.assertEqual(self.store.head(identity), 1)
            self.assertEqual(self.store.history(identity), history)
            self.assertIsNone(self.store.get_operating_operation(operation, limits=LIMITS))
        # Empty evidence remains meaningful for reducing an incomplete setup.
        for outcome in ("deny", "revoke"):
            signed = self.reduction(signed, outcome, [], "empty-" + outcome)
            self.commit(signed, revoker_policy())
        self.assertEqual(self.store.head(identity), 3)

    def test_reductions_use_historical_declarations_without_fresh_availability(self):
        """Deny/revoke use the bound setup after membership changes, artifact loss and approver withdrawal."""
        setup, source, records = short_note(self.store)
        permission = scope("main_research", data=True)
        signed = sign(decision(prepare(self.store, permission), permission))
        original = self.commit(signed)
        successor = replace(setup, declarations=[declaration("new-only")],
            readiness=readiness("incomplete_intake"), supersedes=ref("project", "supersedes", "project"))
        self.store.submit_typed(request("new-setup", [project_envelope("project", 2, successor, CREATOR)], {"project": 1}))
        for artifact in (source.originals[0].artifact, records[-2].artifact_references[0], records[-1].artifact_references[0]):
            (self.root / "objects" / artifact.digest).unlink()
        with patch.object(ArtifactStore, "verify", side_effect=AssertionError("historical reduction read artifact")), \
                patch.object(ArtifactStore, "_verify_for_commit", side_effect=AssertionError("historical reduction synchronized artifact")), \
                patch("research_pipeline.operating_authority_store._resolve", side_effect=AssertionError("historical reduction resolved fresh dossier")), \
                patch("research_pipeline.operating_authority_store._fresh", side_effect=AssertionError("historical reduction required readiness")), \
                patch.object(RecordStore, "get_typed_revision", side_effect=AssertionError("unbounded typed read")):
            for outcome in ("deny", "revoke"):
                before = metadata(self.root)
                invalid = self.reduction(signed, outcome, ["new-only"], "new-only-" + outcome)
                with self.subTest(outcome=outcome), self.assertRaises(a.AuthorityReadinessError):
                    self.commit(invalid, revoker_policy())
                self.assertEqual(metadata(self.root), before)
                self.assertIsNone(self.store.get_operating_operation("new-only-" + outcome, limits=LIMITS))
                signed = self.reduction(signed, outcome, ["seed-note"], "historical-" + outcome)
                result = self.commit(signed, revoker_policy())
                # Reconciliation must bypass even the new historical declaration read.
                with patch("research_pipeline.operating_authority_store._historical_declarations",
                           side_effect=AssertionError("retry rechecked setup")):
                    self.assertEqual(self.store.commit_operating_decision(signed, policy=None,
                        evaluated_at=None, limits=LIMITS), result)
                    self.assertEqual(self.store.get_operating_operation("approve", limits=LIMITS), original)
        history = self.store.inspect_operating_history("synthetic", "project", policy=revoker_policy(), limits=LIMITS).to_dict()
        self.assertEqual([entry["signature_status"] for entry in history["decisions"]], ["unavailable", "verified", "verified"])
        self.assertEqual([entry["envelope"]["content"]["decision"]["binding"]["project"]["revision"]
                          for entry in history["decisions"]], [1, 1, 1])

    def test_approval_and_initial_denial_still_reject_unknown_declarations(self):
        """Shared stored membership validation preserves both initial decision branches."""
        empty(self.store)
        binding = prepare(self.store, scope())
        before = metadata(self.root)
        for outcome in ("approve", "deny"):
            value = decision(binding, scope() if outcome == "approve" else None,
                outcome=outcome, operation="unknown-" + outcome).to_dict()
            value["judgments"]["evidence_declarations"] = ["nonexistent"]
            with self.subTest(outcome=outcome), self.assertRaises(a.AuthorityReadinessError):
                self.commit(sign(a.OperatingDecision(value)))
            self.assertEqual(metadata(self.root), before)

    def test_historical_setup_integrity_and_independent_read_limits(self):
        """Historical setup digest and read allowances fail before a reduction can append."""
        from research_pipeline import operating_authority_store as module
        empty(self.store)
        # A legitimate larger local setup makes its typed retention the peak,
        # independently of the compact decision's original-request recovery.
        setup = self.store.get_typed_revision("project", 1)[1]
        successor = replace(setup, limitations=["Synthetic bounded metadata " + "x" * 16000] * 4,
            supersedes=ref("project", "supersedes", "project"))
        self.store.submit_typed(request("larger-setup", [project_envelope("project", 2, successor, CREATOR)], {"project": 1}))
        binding = self.store.prepare_operating_binding(ref("project", "project_setup", "project", 2),
            scope=scope(), limits=LIMITS)
        signed = sign(decision(binding, scope()))
        self.commit(signed)
        connection = self.store._connection
        content = connection.execute("SELECT content_json FROM revisions WHERE record_id='project' AND revision=2").fetchone()[0]
        for outcome in ("deny", "revoke"):
            reduced = self.reduction(signed, outcome, [], "bounded-" + outcome)
            # A changed historical envelope must fail its full digest comparison.
            connection.execute("UPDATE revisions SET content_json='{}' WHERE record_id='project' AND revision=2")
            with self.assertRaises(a.AuthorityIntegrityError):
                self.commit(reduced, revoker_policy())
            connection.execute("UPDATE revisions SET content_json=? WHERE record_id='project' AND revision=2", (content,))
            before = metadata(self.root)
            observed = {}
            check = module._historical_declarations

            def observe(reader, value):
                """Measure real pre-check consumption while delegating the exact historical setup validation."""
                observed["entered"] = True
                observed["references"] = reader.references
                result = check(reader, value)
                observed["typed_retention"] = reader.metadata_bytes
                return result

            # A real rolled-back append supplies thresholds without committing the
            # candidate, so both below-bound retries exercise the same predecessor.
            def rollback(point):
                """Abort at actual insertion after all historical read limits have been measured."""
                if point == "after_first_revision":
                    raise RuntimeError("rollback measured reduction")

            with patch.object(module, "_historical_declarations", observe), \
                    patch("research_pipeline.store._fault", rollback), self.assertRaises(RuntimeError):
                self.commit(reduced, revoker_policy())
            self.assertEqual(metadata(self.root), before)
            for limits in (replace(LIMITS, max_metadata_bytes=observed["typed_retention"] - 1),
                           replace(LIMITS, max_references=observed["references"])):
                observed["entered"] = False
                with self.subTest(outcome=outcome, limits=limits), \
                        patch.object(module, "_historical_declarations", observe), \
                        patch("research_pipeline.project.decode_envelope", side_effect=AssertionError("unreserved typed setup")), \
                        self.assertRaises(a.AuthorityLimitError):
                    self.store.commit_operating_decision(reduced, policy=revoker_policy(), evaluated_at=TIME, limits=limits)
                self.assertTrue(observed["entered"])
                self.assertEqual(metadata(self.root), before)
                self.assertIsNone(self.store.get_operating_operation("bounded-" + outcome, limits=LIMITS))
