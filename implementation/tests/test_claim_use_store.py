"""Real transactional claim-use binding, reassessment, rollback and exact-history tests."""

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

from research_pipeline.claim_use import (
    ClaimUse, ClaimUseLimitError, ClaimUseIntegrityError, ClaimUsePremise, ClaimUseRoute,
    encode_envelope as use_envelope,
)
from research_pipeline import claim_use_store
from research_pipeline.artifacts import ArtifactIntegrityError, ArtifactNotFoundError
from research_pipeline.domain import DomainValidationError, RecordEnvelope
from research_pipeline.scientific import encode_envelope
from research_pipeline.store import (
    RecordStore, ReferenceResolutionError, RevisionConflictError, RecordNotFoundError,
    StoreLayoutError, SubmissionConflictError,
)
from research_pipeline.backup import create_backup, restore_backup, inspect_backup, BackupError
from tests.claim_use_fixtures import (
    PROVENANCE, LIMITS, ref, batch, binding, issue, review, populate, assessment_envelope,
)


def metadata(root):
    """Snapshot every application table, including resources and all freshness projections."""
    with sqlite3.connect(Path(root)/"metadata.sqlite3") as connection:
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {table: list(connection.execute(f'SELECT * FROM "{table}" ORDER BY 1,2')) for table in tables}


class ClaimUseStoreTests(unittest.TestCase):
    """Disposable stores exercise complete observable transactions with existing unittest patterns."""

    def setUp(self):
        """Allocate independent outside-source runtime paths and close handles before cleanup."""
        temporary = TemporaryDirectory(dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=4)
        self.addCleanup(self.store.close)
        self.artifact, self.initial, self.receipt = populate(self.store)

    def inspect(self, identity="use"):
        """Return a detached current view under explicit finite limits."""
        return self.store.inspect_claim_use(identity, limits=LIMITS).to_dict()

    def generation(self, identity="use"):
        """Observe only the generation through the actual coherent public read."""
        return self.inspect(identity)["generation"]

    def reject(self, request, error=ReferenceResolutionError, *, typed=True):
        """Assert every table is unchanged on admission failure, without hiding diagnostics."""
        before = metadata(self.root)
        with self.assertRaises(error):
            (self.store.submit_typed if typed else self.store.submit)(request)
        self.assertEqual(metadata(self.root), before)

    def append(self, identity, value, *, typed=True):
        """Append an assertion through either public path with ordinary expected-head CAS."""
        revision = (self.store.head(identity) or 0)+1
        request = batch(f"change-{identity}-{revision}", [assessment_envelope(identity, revision, value, PROVENANCE)])
        receipt = (self.store.submit_typed if typed else self.store.submit)(request)
        return request, receipt

    def test_initial_perpetual_ineligibility_detachment_and_historical_receipts(self):
        """Favorable reports never promote; current views cannot mutate historical pins or receipts."""
        old = self.store.get_typed_revision("use", 1)
        view = self.inspect()
        self.assertEqual(view["generation"], 1)
        self.assertFalse(view["eligible"])
        self.assertTrue(view["requires_reassessment"])
        self.assertEqual(len(view["routes"]), 2)
        self.assertFalse(view["authorized_disposition"]["available"])
        self.assertEqual(view["attachment_availability"], "not_checked_metadata_only")
        view["routes"].clear()
        self.assertEqual(len(self.inspect()["routes"]), 2)
        self.append("review-a", replace(review(), reviewer="New report"))
        self.assertEqual(self.generation(), 2)
        self.assertEqual(self.generation("downstream-use"), 2)
        self.assertEqual(self.generation("unrelated-use"), 1)
        self.assertEqual(self.store.get_typed_revision("use", 1), old)
        self.assertEqual(self.store.submit_typed(self.initial), self.receipt)
        self.assertFalse(self.inspect()["eligible"])

    def test_withdrawal_issue_link_removal_resolution_reopening_and_association(self):
        """Every relevant assertion revision coalesces once and history union retains removed targets."""
        withdrawal = replace(review(), route_assessments=[replace(review().route_assessments[0], outcome="stale")])
        self.append("review-a", withdrawal, typed=False)
        self.append("issue", issue(), typed=False)
        self.append("issue", replace(issue("unrelated", "claim"), disposition="resolved"))
        self.append("issue", issue("unrelated", "claim"))
        self.append("association", issue("review-b", "review"))
        self.append("chain", issue("association", "issue"))
        self.assertEqual(self.generation(), 7)
        self.assertEqual(self.generation("downstream-use"), 7)
        self.assertEqual(self.generation("unrelated-use"), 3)
        self.assertEqual(self.store.head("candidate"), 1)
        observed = self.inspect()["observed_assertions"]
        self.assertIn("issue", {v["pin"]["record_id"] for v in observed})
        self.assertEqual(self.store.get_typed_revision("issue", 1)[1].disposition, "open")

    def test_pinned_successor_scope_change_is_separate_from_historical_assessment(self):
        """Identity watches expose changed scope without substituting the bound Review pin."""
        successor = replace(review(), target_context=ref("other-scope", "target_context", "research_context"),
                            route_assessments=[])
        self.append("review-a", successor)
        view = self.inspect()
        self.assertEqual(view["generation"], 2)
        reported = next(r for r in view["observed_assertions"] if r["pin"]["record_id"] == "review-a")
        self.assertEqual(reported["pin"]["revision"], 2)
        self.assertFalse(reported["still_assesses_bound_route"])
        self.assertEqual(view["historical_pins"]["assessments"][0]["revision"], 1)
        self.assertEqual(view["context"]["record_id"], "scope")
        self.assertFalse(view["eligible"])

    def test_direct_issue_updates_use_and_downstream_on_both_submission_paths(self):
        """Exact use targets advance atomically, remain observed after removal, and retry once."""
        for typed in (False, True):
            root = self.parent/f"direct-{typed}"
            with self.subTest(typed=typed), RecordStore.create(root, schema_version=4) as store:
                populate(store)
                original = store.get_typed_revision("use", 1)
                candidate = store.get_typed_revision("candidate", 1)
                value = issue("use", "promotion_eligibility")
                request = batch("direct", [assessment_envelope("use-issue", 1, value, PROVENANCE)])
                submit = store.submit_typed if typed else store.submit
                receipt = submit(request)
                direct = dict(type="binding_affected", assertion=claim_use_store.keypin(("use-issue", 1), "issue"),
                              binding=claim_use_store.keypin(("use", 1)))
                downstream = dict(type="upstream_affected", upstream_binding=claim_use_store.keypin(("use", 1)))
                for identity in ("use", "downstream-use", "unrelated-use"):
                    view = store.inspect_claim_use(identity, limits=LIMITS).to_dict()
                    self.assertEqual(view["generation"], 1 if identity == "unrelated-use" else 2)
                    self.assertFalse(view["eligible"])
                    self.assertFalse(view["authorized_disposition"]["available"])
                    if identity != "unrelated-use":
                        transition = view["mechanical_freshness"]["last_transition"]
                        self.assertEqual(transition["event_id"], receipt.event_id)
                        self.assertIn(direct if identity == "use" else downstream, transition["causes"])
                        observation = next(a for a in view["observed_assertions"] if a["pin"]["record_id"] == "use-issue")
                        self.assertEqual(observation, dict(pin=claim_use_store.keypin(("use-issue", 1), "issue"),
                            content=value.to_dict(), attributed=True, still_assesses_bound_route=None))
                self.assertEqual(submit(request), receipt)
                self.assertEqual(store.inspect_claim_use("use", limits=LIMITS).to_dict()["generation"], 2)
                # Resolution, target removal and reopening retain the established
                # exact binding relevance through the assertion history union.
                for revision, disposition in ((2, "resolved"), (3, "open")):
                    successor = replace(value, affected_records=[ref("unrelated", "affected_record", "claim")],
                                        disposition=disposition)
                    submit(batch(f"successor-{revision}", [assessment_envelope("use-issue", revision, successor, PROVENANCE)]))
                    for identity in ("use", "downstream-use"):
                        view = store.inspect_claim_use(identity, limits=LIMITS).to_dict()
                        self.assertEqual(view["generation"], revision+1)
                        self.assertIn(claim_use_store.keypin(("use-issue", revision), "issue"),
                                      [a["pin"] for a in view["observed_assertions"]])
                self.assertEqual(submit(request), receipt)
                for identity in ("use", "downstream-use"):
                    self.assertEqual(store.inspect_claim_use(identity, limits=LIMITS).to_dict()["generation"], 4)
                self.assertEqual(store.get_typed_revision("use", 1), original)
                self.assertEqual(store.get_typed_revision("candidate", 1), candidate)
                self.assertEqual(store.head("candidate"), 1)

    def test_direct_issue_needs_only_registration_not_routes_or_incoming_edges(self):
        """A leaf binding is its own anchor; a generic promotion document never registers a use."""
        _, receipt = self.append("leaf-issue", issue("unrelated-use", "promotion_eligibility"))
        view = self.inspect("unrelated-use")
        self.assertEqual(view["routes"], [])
        self.assertEqual(view["generation"], 2)
        self.assertEqual(view["mechanical_freshness"]["last_transition"]["event_id"], receipt.event_id)
        self.assertIn("leaf-issue", {a["pin"]["record_id"] for a in view["observed_assertions"]})
        self.assertEqual((self.generation(), self.generation("downstream-use")), (1, 1))
        self.store.submit(batch("generic", [RecordEnvelope("opaque", 1, "promotion_eligibility", {}, PROVENANCE)]))
        before = metadata(self.root)
        self.append("generic-issue", issue("opaque", "promotion_eligibility"))
        after = metadata(self.root)
        for table in ("claim_use_bindings", "claim_use_current", "claim_use_generations"):
            self.assertEqual(after[table], before[table])
        with self.assertRaises(RecordNotFoundError):
            self.inspect("opaque")

    def test_direct_historical_binding_target_leaves_replacement_unaffected(self):
        """Old U@1 remains an impact/observation anchor only in views that actually visit it."""
        self.store.submit_typed(batch("rebind-direct", [use_envelope("use", 2, binding("unrelated", (), (), ()), PROVENANCE)]))
        self.append("old-binding-issue", issue("use", "promotion_eligibility"))
        current, downstream = self.inspect(), self.inspect("downstream-use")
        self.assertEqual((current["generation"], downstream["generation"], self.generation("unrelated-use")), (2, 2, 1))
        self.assertNotIn("old-binding-issue", {a["pin"]["record_id"] for a in current["observed_assertions"]})
        self.assertIn("old-binding-issue", {a["pin"]["record_id"] for a in downstream["observed_assertions"]})
        self.assertEqual(downstream["upstream_bindings"][0]["binding"], claim_use_store.keypin(("use", 1)))
        self.assertEqual(self.store.get_typed_revision("use", 1)[1], binding())

    def test_forward_same_batch_issue_binding_has_identical_prospective_view(self):
        """Forward direct targets coalesce registration and assertion causes at generation one."""
        views, accounts = {}, {}
        original = claim_use_store._inspection

        def capture(reader, identity, limits):
            """Retain the actual prospective result and its independent bounded work account."""
            result = original(reader, identity, limits)
            views[identity], accounts[identity] = result.to_dict(), dict(reader.counts)
            return result

        request = batch("forward-direct", [assessment_envelope("forward-issue", 1,
                        issue("forward-use", "promotion_eligibility"), PROVENANCE),
                        use_envelope("forward-use", 1, binding("unrelated", (), (), ()), PROVENANCE)])
        with patch.object(claim_use_store, "_inspection", capture):
            receipt = self.store.submit_typed(request)
        prospective, prospective_account = views["forward-use"], accounts["forward-use"]
        with patch.object(claim_use_store, "_inspection", capture):
            persisted = self.inspect("forward-use")
        self.assertEqual(prospective["mechanical_freshness"]["last_transition"]["event_id"], 2**63-1)
        prospective["mechanical_freshness"]["last_transition"]["event_id"] = receipt.event_id
        self.assertEqual(prospective, persisted)
        self.assertEqual(persisted["generation"], 1)
        self.assertEqual({c["type"] for c in persisted["mechanical_freshness"]["reasons"]},
                         {"binding_registered", "binding_affected"})
        self.assertIn("forward-issue", {a["pin"]["record_id"] for a in persisted["observed_assertions"]})
        for dimension in ("metadata_bytes", "index_rows", "assertion_revisions"):
            self.assertGreaterEqual(prospective_account[dimension], accounts["forward-use"][dimension])

    def test_unrelated_context_policy_and_events_do_not_advance(self):
        """Independent context reports and generic policy/global changes confer no freshness effect."""
        self.append("independent-review", replace(review(), target_context=ref("other-scope", "target_context", "research_context")))
        self.append("independent-issue", issue("unrelated", "claim"))
        old = self.store.get_typed_revision("scope", 1)[1]
        self.store.submit_typed(batch("context-next", [encode_envelope("scope", 2, replace(old, question="Active scope changed"), PROVENANCE)]))
        self.store.submit(batch("policy-next", [RecordEnvelope("policy", 2, "decision", {"new": True}, PROVENANCE)]))
        self.store.submit(batch("global", [RecordEnvelope("global", 1, "event", {}, PROVENANCE)]))
        self.assertEqual(self.generation(), 1)
        self.assertEqual(self.generation("downstream-use"), 1)
        self.assertEqual(self.generation("unrelated-use"), 2)
        self.assertEqual(self.inspect()["context"]["revision"], 1)

    def test_rebind_preserves_old_upstream_and_propagates_through_it(self):
        """Downstream U@1 pins survive U@2; changes to U@1 still reach downstream D."""
        rebind = use_envelope("use", 2, binding("unrelated", (), (), ()), PROVENANCE)
        self.store.submit_typed(batch("rebind", [rebind]))
        self.assertEqual((self.generation(), self.generation("downstream-use")), (2, 1))
        self.append("review-a", replace(review(), reviewer="Withdrawn old route"))
        self.assertEqual((self.generation(), self.generation("downstream-use")), (2, 2))
        upstream = self.inspect("downstream-use")["upstream_bindings"]
        self.assertEqual(upstream[0]["binding"]["revision"], 1)
        self.assertEqual(self.store.get_typed_revision("use", 1)[1], binding())
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.inspect_claim_use("downstream-use", limits=LIMITS).to_dict()["generation"], 2)

    def test_same_batch_forward_associations_multiple_causes_coalesce(self):
        """Forward Issue chains and simultaneous assessment changes share one transition event."""
        request = batch("coalesced", [assessment_envelope("chain", 1, issue("peer", "issue"), PROVENANCE),
                         assessment_envelope("peer", 1, issue("review-a", "review"), PROVENANCE),
                         assessment_envelope("review-a", 2, replace(review(), reviewer="changed"), PROVENANCE)])
        self.store.submit(request)
        self.assertEqual((self.generation(), self.generation("downstream-use")), (2, 2))
        history = self.store.claim_use_history("use", limits=LIMITS).to_dict()["transitions"]
        self.assertGreater(len(history[-1]["causes"]), 2)
        self.assertEqual(self.store.submit_typed(request), self.store.get_submission("coalesced"))
        self.assertEqual(self.generation(), 2)

    def test_generic_no_bypass_and_stable_registration_identity(self):
        """Generic registration receives the same checks and cannot replace registered content."""
        generic = use_envelope("generic-use", 1, binding(), PROVENANCE)
        self.store.submit(batch("generic-use", [generic]))
        self.assertEqual(self.generation("generic-use"), 1)
        self.reject(batch("opaque", [RecordEnvelope("use", 2, "promotion_eligibility", {}, PROVENANCE)]), typed=False)
        self.store.submit(batch("historical-generic", [RecordEnvelope("generic", 1, "promotion_eligibility", {}, PROVENANCE)]))
        self.reject(batch("convert", [use_envelope("generic", 2, binding(), PROVENANCE)]), typed=False)
        for kind in ("review", "issue"):
            self.reject(batch("opaque-"+kind, [RecordEnvelope("opaque-"+kind, 1, kind, {}, PROVENANCE)]), typed=False)
        self.assertEqual(self.store.get_revision("generic", 1).content, {})

    def test_bad_pairings_and_conjunctions_fail_atomically(self):
        """Route conclusion, complete premise conjunction, assessment context and policy are exact."""
        value = binding()
        values = [replace(value, candidate_claim=ref("downstream", "candidate_claim", "claim")),
                  replace(value, routes=[replace(value.routes[0], premises=[])]),
                  replace(value, routes=[replace(value.routes[0], premises=[ClaimUsePremise(ref("premise-b", "premise", "claim"), None)])]),
                  replace(value, target_context=ref("other-scope", "target_context", "research_context")),
                  replace(value, routes=[replace(value.routes[0], assessments=[ref("review-d", "support_assessment", "review")])])]
        self.store.submit(batch("other-policy", [RecordEnvelope("other-policy", 1, "decision", {}, PROVENANCE)]))
        values.append(replace(value, policies=[ref("other-policy", "authorization_policy", "decision")]))
        for i, bad in enumerate(values):
            with self.subTest(i=i):
                self.reject(batch(f"bad-{i}", [use_envelope(f"bad-{i}", 1, bad, PROVENANCE)]))

    def test_unsupported_wrong_kind_absent_and_generic_upstream(self):
        """Required typed pins cannot borrow opaque or shallow records as registered support."""
        self.store.submit(batch("opaque-support", [RecordEnvelope("opaque", 1, "promotion_eligibility", {}, PROVENANCE)]))
        self.reject(batch("bad-upstream", [use_envelope("bad", 1, binding(upstream="opaque"), PROVENANCE)]))
        self.reject(batch("wrong-upstream-candidate", [use_envelope("bad", 1, binding(upstream="use"), PROVENANCE)]))
        self.reject(batch("absent", [use_envelope("bad", 1, replace(binding(), candidate_claim=ref("absent", "candidate_claim", "claim")), PROVENANCE)]))
        self.store.submit(batch("opaque-claim", [RecordEnvelope("opaque-claim", 1, "claim", {}, PROVENANCE,
                                                    scientific_disposition="provisional")]))
        self.reject(batch("untyped", [use_envelope("bad", 1, binding("opaque-claim", (), (), ()), PROVENANCE)]))

    def test_direct_self_support_is_rejected_but_descriptive_graph_remains_readable(self):
        """Existing scientific descriptive cycles do not establish permitted deductive support."""
        route = self.store.get_typed_revision("route-a", 1)[1]
        circular = replace(route, premises=[ref("candidate", "premise", "claim")])
        self.store.submit_typed(batch("descriptive", [encode_envelope("circular-route", 1, circular, PROVENANCE),
            assessment_envelope("circular-review", 1, review(route="circular-route"), PROVENANCE)]))
        value = binding(routes=("circular-route",), assessments=("circular-review",), premises=("candidate",))
        self.reject(batch("circular", [use_envelope("circular", 1, value, PROVENANCE)]))
        self.assertEqual(self.store.get_typed_revision("circular-route", 1)[1], circular)

    def test_direct_artifact_damage_rejects_new_binding_but_not_inspection_or_retry(self):
        """New bindings verify required direct bytes; current reads/retries remain metadata-only."""
        path = self.root/"objects"/self.artifact.digest
        path.chmod(0o600)
        path.write_bytes(b"damaged")
        self.reject(batch("damaged", [use_envelope("damaged", 1, binding(), PROVENANCE)]), ArtifactIntegrityError)
        self.assertEqual(self.generation(), 1)
        self.assertEqual(self.store.submit_typed(self.initial), self.receipt)
        with self.assertRaises(ArtifactIntegrityError):
            self.store.get_revision("evidence", 1)

    def test_failures_before_and_after_freshness_and_lost_ack(self):
        """All pre-COMMIT effects roll back; lost acknowledgment reconciles the original receipt."""
        request = batch("atomic", [assessment_envelope("review-a", 2, review(), PROVENANCE)])
        for boundary in ("before_metadata", "after_first_revision", "after_claim_use_updates"):
            before = metadata(self.root)
            def fail(point):
                """Inject failure only at the selected actual transaction boundary."""
                if point == boundary:
                    raise RuntimeError(point)
            with patch("research_pipeline.store._fault", fail), self.assertRaisesRegex(RuntimeError, boundary):
                self.store.submit_typed(request)
            self.assertEqual(metadata(self.root), before)
        def lost(point):
            """Raise after SQLite COMMIT has left rollback handling."""
            if point == "after_commit":
                raise RuntimeError("lost acknowledgment")
        with patch("research_pipeline.store._fault", lost), self.assertRaises(RuntimeError):
            self.store.submit_typed(request)
        receipt = self.store.get_submission("atomic")
        self.assertEqual(self.generation(), 2)
        self.assertEqual(self.store.submit(request), receipt)
        self.assertEqual(self.generation(), 2)
        changed = batch("atomic", [assessment_envelope("review-a", 2, replace(review(), reviewer="conflict"), PROVENANCE)])
        self.reject(changed, SubmissionConflictError)

    def test_independent_handle_stale_head_and_exact_retry(self):
        """Serialized expected-head CAS rejects stale submissions without freshness effects."""
        with RecordStore.open(self.root) as other:
            request, receipt = self.append("review-a", review())
            before = metadata(self.root)
            with self.assertRaises(RevisionConflictError):
                other.submit_typed(batch("stale", [assessment_envelope("review-a", 2, review(), PROVENANCE)]))
            self.assertEqual(metadata(self.root), before)
            self.append("review-a", replace(review(), reviewer="later"))
            self.assertEqual(other.submit_typed(request), receipt)
            self.assertEqual(self.generation(), 3)

    def test_bounded_history_pages_and_missing_id(self):
        """Pages never omit within-page transitions and expose a precise generation cursor."""
        for i in range(3):
            self.append("review-a", replace(review(), reviewer=str(i)))
        first = self.store.claim_use_history("use", limit=2, limits=LIMITS).to_dict()
        self.assertEqual([x["generation"] for x in first["transitions"]], [1, 2])
        self.assertEqual(first["next_cursor"], 2)
        second = self.store.claim_use_history("use", after_generation=2, limit=2, limits=LIMITS).to_dict()
        self.assertEqual([x["generation"] for x in second["transitions"]], [3, 4])
        self.assertIsNone(second["next_cursor"])
        for kwargs in ({"limit": True}, {"limit": 257}, {"after_generation": -1}, {"after_generation": 2**63}):
            with self.assertRaises(DomainValidationError):
                self.store.claim_use_history("use", limits=LIMITS, **kwargs)
        for method in (self.store.inspect_claim_use, self.store.claim_use_history):
            with self.assertRaises(RecordNotFoundError):
                method("missing", limits=LIMITS)

    def test_inspection_independent_bounds_and_generation_overflow(self):
        """Read bounds and Review/direct-Issue generation overflow fail without metadata effects."""
        for field in ("max_bindings", "max_records", "max_references", "max_metadata_bytes", "max_result_bytes"):
            with self.subTest(field=field), self.assertRaises(ClaimUseLimitError):
                self.store.inspect_claim_use("downstream-use", limits=replace(LIMITS, **{field: 1}))
        with sqlite3.connect(self.root/"metadata.sqlite3") as connection:
            connection.execute("UPDATE claim_use_current SET generation=? WHERE use_id='use'", (2**63-1,))
        self.reject(batch("overflow", [assessment_envelope("review-a", 2, review(), PROVENANCE)]), ClaimUseLimitError)
        self.reject(batch("direct-overflow", [assessment_envelope("direct-issue", 1,
                    issue("use", "promotion_eligibility"), PROVENANCE)]), ClaimUseLimitError)

    def test_index_work_transition_and_cause_limits_fail_before_metadata(self):
        """Independent planner ceilings reject whole writes rather than truncating propagation."""
        for dimension in ("bindings", "index_rows", "transitions", "causes", "assertion_revisions", "references", "metadata_bytes"):
            original = claim_use_store.Reader.__init__
            def limited(reader, *args, **kwargs):
                """Reduce one immutable test-local operation budget after ordinary initialization."""
                original(reader, *args, **kwargs)
                reader.caps[dimension] = 0
            with self.subTest(dimension=dimension), patch.object(claim_use_store.Reader, "__init__", limited):
                self.reject(batch("bound", [assessment_envelope("review-a", 2, review(), PROVENANCE)]), ClaimUseLimitError)

    def test_open_rejects_missing_extra_and_corrupt_projections(self):
        """Open checks exact temporal rows and chronological effects, including missing/extra metadata."""
        self.append("review-a", review())
        changes = ("DELETE FROM claim_use_generations WHERE use_id='use' AND generation=2",
                   "DELETE FROM claim_use_dependencies WHERE use_id='use' AND ordinal=0",
                   "UPDATE claim_use_generations SET causes_json='[]' WHERE use_id='use' AND generation=2",
                   "DELETE FROM claim_use_current WHERE use_id='use'",
                   "UPDATE claim_use_current SET generation=1 WHERE use_id='use'",
                   "UPDATE claim_use_origin SET event_watermark=1",
                   "DELETE FROM claim_use_revision_events WHERE record_id='candidate'",
                   "UPDATE claim_use_revision_events SET event_id=1 WHERE record_id='candidate'",
                   "INSERT INTO claim_use_revision_events VALUES ('invented',1,1)",
                   "DELETE FROM claim_use_association_links WHERE record_id='review-a' AND ordinal=0",
                   "UPDATE claim_use_association_links SET ordinal=99 WHERE record_id='review-a' AND ordinal=0",
                   "UPDATE claim_use_association_links SET relationship='affected_record' WHERE record_id='review-a' AND ordinal=0",
                   "UPDATE claim_use_association_links SET target_revision=2 WHERE record_id='review-a' AND ordinal=0",
                   "UPDATE claim_use_association_links SET event_id=1 WHERE record_id='review-a'",
                   "INSERT INTO claim_use_association_links VALUES ('candidate',1,99,2,'affected_record','candidate',1)",
                   "UPDATE claim_use_dependencies SET registration_event=1 WHERE use_id='use'",
                   "UPDATE claim_use_upstreams SET registration_event=1 WHERE use_id='downstream-use'")
        import shutil
        for i, sql in enumerate(changes):
            target = self.parent/f"corrupt-{i}"
            shutil.copytree(self.root, target)
            with sqlite3.connect(target/"metadata.sqlite3") as connection:
                connection.execute(sql)
            with self.subTest(sql=sql), self.assertRaises(StoreLayoutError):
                RecordStore.open(target)

    def test_earlier_schema_generic_marker_mentions_do_not_select_registration(self):
        """An explicit root discriminator alone selects ClaimUse; prose and nested data stay generic."""
        from research_pipeline.claim_use import FORMAT
        with RecordStore.create(self.parent/"generic-old") as old:
            records = [RecordEnvelope("prose", 1, "promotion_eligibility", {"note": FORMAT}, PROVENANCE),
                       RecordEnvelope("nested", 1, "decision", {"nested": {"format": FORMAT}}, PROVENANCE)]
            receipt = old.submit(batch("generic", records))
            self.assertEqual(old.submit(batch("generic", records)), receipt)
            self.assertEqual(old.get_revision("nested", 1), records[1])

    def test_exact_backup_restore_and_explicit_migration(self):
        """Schema4 snapshots preserve exact SQL bytes and original receipts; schema3 stays explicit."""
        self.append("issue", issue())
        exported = self.parent/"backup"
        create_backup(self.store, exported)
        inspect_backup(exported)
        with restore_backup(exported, self.parent/"restored") as restored:
            self.assertEqual(restored.inspect_claim_use("use", limits=LIMITS), self.store.inspect_claim_use("use", limits=LIMITS))
            self.assertEqual(restored.submit_typed(self.initial), self.receipt)
            self.assertEqual(metadata(self.parent/"restored"), metadata(self.root))
        old_root = self.parent/"old"
        with RecordStore.create(old_root, schema_version=3) as old:
            old.submit(batch("old-generic", [RecordEnvelope("opaque-review", 1, "review", {}, PROVENANCE)]))
            before = metadata(old_root)
            for operation in (lambda: old.inspect_claim_use("use", limits=LIMITS),
                              lambda: old.submit_typed(batch("use", [use_envelope("use", 1, binding(), PROVENANCE)]))):
                with self.assertRaises(StoreLayoutError):
                    operation()
            self.assertEqual(metadata(old_root), before)
            create_backup(old, self.parent/"old-backup")
        with restore_backup(self.parent/"old-backup", self.parent/"migrated", target_schema=4,
                            migration_provenance=PROVENANCE) as migrated:
            after = metadata(self.parent/"migrated")
            for name in before:
                if name != "migration_history":
                    self.assertEqual(after[name], before[name])
            self.assertEqual(migrated.get_revision("opaque-review", 1).content, {})
            self.assertEqual(after["claim_use_origin"], [(1, 1)])
            self.assertEqual(after["claim_use_bindings"], [])
            create_backup(migrated, self.parent/"migrated-backup")
