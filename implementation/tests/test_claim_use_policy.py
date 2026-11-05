"""Schema-5 exact policy observations, historical impact and coalesced origin causes."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import claim_use_store
from research_pipeline.claim_use import ClaimUsePremise, ClaimUseRoute, encode_envelope as use_envelope
from research_pipeline.domain import DomainValidationError, RecordEnvelope
from research_pipeline.scientific import Claim, Justification, encode_envelope
from research_pipeline.store import RecordStore
from tests.claim_use_fixtures import (
    populate, binding, batch, ref, review, issue, assessment_envelope, PROVENANCE, LIMITS,
)
from tests.test_claim_use_store import metadata


def policy_record(identity="policy", revision=2, text="Prose-only successor"):
    """Create a generic shallow declaration; its content makes no authority claim."""
    return RecordEnvelope(identity, revision, "decision", {"declaration": text}, PROVENANCE)


def exact(identity, revision=1, kind="decision"):
    """Specify expected public exact-pin dictionaries independently of product helpers."""
    return dict(record_id=identity, revision=revision, target_kind=kind)


class PolicyFreshnessTests(unittest.TestCase):
    """Exercise real public generic and typed writes against independent schema-5 stores."""

    def setUp(self):
        """Create disposable state; each test owns its store, artifacts and graph."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)/"store"
        self.store = RecordStore.create(self.root, schema_version=5)
        self.addCleanup(self.store.close)
        self.artifact, self.initial, self.receipt = populate(self.store)

    def view(self, identity="use"):
        """Read one complete coherent metadata-only public inspection."""
        return self.store.inspect_claim_use(identity, limits=LIMITS).to_dict()

    def test_prose_successor_exact_causes_and_attribution(self):
        """A prose-only policy successor increments once, retaining evidence and exact old pins."""
        before = metadata(self.root)
        request = batch("policy-change", [policy_record()])
        receipt = self.store.submit(request)
        for identity, ordinal in (("use", 26), ("unrelated-use", 2)):
            view = self.view(identity)
            self.assertEqual((view["version"], view["generation"], view["eligible"]), (2, 2, False))
            cause = dict(type="policy_changed", binding=exact(identity, kind="promotion_eligibility"),
                         dependency_ordinal=ordinal, bound_policy=exact("policy"),
                         previous_policy=exact("policy"), new_policy=exact("policy", 2))
            transition = view["mechanical_freshness"]["last_transition"]
            self.assertEqual(transition["causes"], [cause])
            self.assertEqual((transition["event_id"], transition["submission_id"]),
                             (receipt.event_id, request.submission_id))
            observation = view["observed_policies"][0]
            self.assertEqual(observation, dict(binding=exact(identity, kind="promotion_eligibility"),
                dependency_ordinal=ordinal, bound_policy=exact("policy"), observed_policy=exact("policy", 2),
                observed_content={"declaration": "Prose-only successor"}, attributed=True, superseded=True))
            self.assertIn(dict(type="policy_pin_superseded", **{k: observation[k] for k in
                ("binding", "dependency_ordinal", "bound_policy", "observed_policy")}),
                view["mechanical_freshness"]["reasons"])
            self.assertEqual(view["policy_freshness"], dict(available=True, activation_event_watermark=0))
            self.assertFalse(view["authorized_disposition"]["available"])
        after = metadata(self.root)
        for table in ("claim_use_bindings", "claim_use_dependencies", "claim_use_upstreams", "artifact_links", "artifacts"):
            self.assertEqual(after[table], before[table])
        for table in ("revisions", "record_links"):
            self.assertEqual([r for r in after[table] if r[0] != "policy"],
                             [r for r in before[table] if r[0] != "policy"])
        self.assertEqual(self.store.submit(request), receipt)
        self.assertEqual(self.view()["generation"], 2)
        self.assertEqual(self.store.submit_typed(self.initial), self.receipt)

    def test_selective_historical_binding_and_shallow_mentions(self):
        """U@1/P still affects D pinned to it after current U@2/Q, without repointing either."""
        self.store.submit(batch("q1", [policy_record("q", 1)]))
        rebound = replace(binding("unrelated", (), (), ()), policies=[ref("q", "authorization_policy", "decision")])
        self.store.submit_typed(batch("rebind", [use_envelope("use", 2, rebound, PROVENANCE),
            use_envelope("unrelated-use", 2, rebound, PROVENANCE)]))
        # An Issue merely associates q in its shallow affected-record role.
        # That association must not make q a policy of the historical P binding.
        self.store.submit_typed(batch("mention-q", [assessment_envelope("mention", 1,
            issue("q", "decision"), PROVENANCE)]))
        self.store.submit_typed(batch("review-declares-q", [assessment_envelope("review-a", 2,
            replace(review(), authorization_policy=ref("q", "authorization_policy", "decision")), PROVENANCE)]))
        before = {i: self.view(i)["generation"] for i in ("use", "unrelated-use", "downstream-use")}
        self.store.submit(batch("p2", [policy_record()]))
        self.assertEqual([self.view(i)["generation"] for i in ("use", "unrelated-use", "downstream-use")],
                         [before["use"], before["unrelated-use"], before["downstream-use"]+1])
        downstream = self.view("downstream-use")
        old = next(b for b in downstream["upstream_bindings"] if b["binding"]["record_id"] == "use")
        self.assertEqual(old["binding"], exact("use", kind="promotion_eligibility"))
        self.assertEqual(self.view()["observed_policies"][0]["observed_policy"], exact("q"))
        self.store.submit(batch("q2", [policy_record("q", 2)]))
        self.assertEqual(self.view()["generation"], before["use"]+1)
        self.assertEqual(self.view("downstream-use")["generation"], before["downstream-use"]+1)
        self.store.submit(batch("unrelated-decision", [policy_record("not-policy", 1)]))
        generation = self.view()["generation"]
        self.store.submit(batch("unrelated-successor", [policy_record("not-policy", 2)]))
        self.assertEqual(self.view()["generation"], generation)

    def test_already_advanced_registration_and_same_batch_old_new_pins(self):
        """New and rebound bindings expose advanced heads without fabricated earlier transitions."""
        self.store.submit(batch("p2", [policy_record()]))
        leaf = binding("unrelated", (), (), ())
        self.store.submit_typed(batch("advanced-register", [use_envelope("late", 1, leaf, PROVENANCE)]))
        view = self.view("late")
        self.assertEqual(view["generation"], 1)
        self.assertTrue(view["observed_policies"][0]["superseded"])
        self.assertEqual([c["type"] for c in view["mechanical_freshness"]["last_transition"]["causes"]], ["binding_registered"])
        new_pin = replace(leaf, policies=[ref("policy", "authorization_policy", "decision", 3)])
        request = batch("p3-with-bindings", [use_envelope("late", 2, new_pin, PROVENANCE),
            use_envelope("old-pin", 1, leaf, PROVENANCE), policy_record(revision=3)])
        self.store.submit(request)
        for identity, bound_revision, generation, superseded in (("late", 3, 2, False), ("old-pin", 1, 1, True)):
            view = self.view(identity)
            self.assertEqual(view["generation"], generation)
            self.assertEqual(view["observed_policies"][0]["superseded"], superseded)
            causes = view["mechanical_freshness"]["last_transition"]["causes"]
            policy_cause = next(c for c in causes if c["type"] == "policy_changed")
            self.assertEqual(policy_cause["bound_policy"], exact("policy", bound_revision))
            self.assertEqual(policy_cause["previous_policy"], exact("policy", 2))
            self.assertEqual(policy_cause["new_policy"], exact("policy", 3))

    def test_first_policy_and_forward_upstream_registration_prospective_equals_persisted(self):
        """Complete prospective views include first policies, forward upstreams and successor heads."""
        upstream = replace(binding(), policies=[ref("fresh", "authorization_policy", "decision")], routes=[])
        downstream = replace(binding("downstream", ("route-d",), ("review-d",), ("candidate",), "forward"),
                             policies=[ref("policy", "authorization_policy", "decision")])
        request = batch("forward-new", [use_envelope("forward-down", 1, downstream, PROVENANCE),
            use_envelope("forward", 1, upstream, PROVENANCE), policy_record("fresh", 1), policy_record()])
        original = claim_use_store._inspection
        prospective = {}
        def capture(reader, identity, limits):
            """Retain private pre-insertion complete views while calling the real traversal."""
            result = original(reader, identity, limits)
            if reader.overlay is not None:
                prospective[identity] = result.to_dict()
            return result
        with patch.object(claim_use_store, "_inspection", capture):
            self.store.submit(request)
        for identity, expected in prospective.items():
            persisted = self.view(identity)
            expected["mechanical_freshness"]["last_transition"]["event_id"] = persisted["mechanical_freshness"]["last_transition"]["event_id"]
            self.assertEqual(expected, persisted)
        causes = self.view("forward")["mechanical_freshness"]["last_transition"]["causes"]
        self.assertEqual([c["type"] for c in causes], ["binding_registered"])
        self.assertEqual(len(self.view("forward-down")["observed_policies"]), 2)

    def test_mixed_policy_review_issue_rebinding_has_one_transition(self):
        """A mixed generic batch coalesces distinct policies and assertions with registration."""
        self.store.submit(batch("q1", [policy_record("q", 1)]))
        value = replace(binding(), policies=[ref("policy", "authorization_policy", "decision"),
                                             ref("q", "authorization_policy", "decision")])
        request = batch("combined", [policy_record(), policy_record("q", 2),
            assessment_envelope("review-a", 2, replace(review(), reviewer="Revised prose"), PROVENANCE),
            assessment_envelope("objection", 1, issue("use", "promotion_eligibility"), PROVENANCE),
            use_envelope("use", 2, value, PROVENANCE)])
        self.store.submit(request)
        view = self.view()
        self.assertEqual(view["generation"], 2)
        causes = view["mechanical_freshness"]["last_transition"]["causes"]
        self.assertEqual({c["new_policy"]["record_id"] for c in causes if c["type"] == "policy_changed"}, {"q", "policy"})
        self.assertTrue(any(c["type"] == "binding_registered" for c in causes))
        self.assertTrue(any(c["type"] == "assertion_changed" and c["assertion"]["record_id"] == "review-a" for c in causes))
        self.assertTrue(all("binding" in c for c in causes if c["type"] == "assertion_changed"))
        downstream = self.view("downstream-use")
        self.assertEqual(downstream["generation"], 2)
        self.assertTrue(any(c["type"] == "binding_affected" for c in downstream["mechanical_freshness"]["last_transition"]["causes"]))
        self.assertEqual(len(self.store.claim_use_history("use", limits=LIMITS).to_dict()["transitions"]), 2)

    def test_multiple_origins_survive_late_diamond_arrival_and_conjunction(self):
        """Distinct origins traverse the same edge even when a longer branch arrives later."""
        self.store.submit(batch("q1", [policy_record("q", 1)]))
        # Two different branch candidates make a real conjunction at join.
        records = [encode_envelope(identity, 1, Claim(identity, "synthetic", [],
                   ref("scope", "context", "research_context"), [], [], []), PROVENANCE)
                   for identity in ("joined", "tail-claim")]
        for route, candidate, premises in (("right-route", "unrelated", ("candidate",)),
                ("join-route", "joined", ("downstream", "unrelated")),
                ("join-alt", "joined", ("downstream",)), ("tail-route", "tail-claim", ("joined",))):
            value = Justification(ref("scope", "context", "research_context"),
                [ref(p, "premise", "claim") for p in premises], [], route,
                [ref(candidate, "conclusion", "claim")], [], [])
            assessment = review(candidate, route)
            records.extend([encode_envelope(route, 1, value, PROVENANCE),
                            assessment_envelope(route+"-review", 1, assessment, PROVENANCE)])
        self.store.submit_typed(batch("diamond-science", records))
        left = binding("downstream", ("route-d",), ("review-d",), ("candidate",), "use")
        right = binding("unrelated", ("right-route",), ("right-route-review",), ("candidate",), "use")
        def route_value(route, premises):
            """Declare full ordered conjunctive premises and exact recorded branch pins."""
            return ClaimUseRoute(ref(route, "support_route", "justification"),
                [ClaimUsePremise(ref(c, "premise", "claim"), ref(u, "premise_use", "promotion_eligibility"))
                 for c, u in premises], [ref(route+"-review", "support_assessment", "review")])
        joined = replace(binding("joined", (), (), ()), routes=[
            route_value("join-route", (("downstream", "left"), ("unrelated", "right"))),
            route_value("join-alt", (("downstream", "left"),))],
            policies=[ref("policy", "authorization_policy", "decision"), ref("q", "authorization_policy", "decision")])
        tail = replace(binding("tail-claim", (), (), ()),
                       routes=[route_value("tail-route", (("joined", "join"),))])
        self.store.submit_typed(batch("diamond-register", [use_envelope(i, 1, v, PROVENANCE)
            for i, v in (("tail", tail), ("join", joined), ("left", left), ("right", right))]))
        self.store.submit(batch("origins", [policy_record(), policy_record("q", 2),
            assessment_envelope("review-a", 2, replace(review(), reviewer="Origin two"), PROVENANCE)]))
        causes = self.view("join")["mechanical_freshness"]["last_transition"]["causes"]
        self.assertEqual({c["binding"]["record_id"] for c in causes if c["type"] == "policy_changed"},
                         {"use", "left", "right", "join"})
        self.assertTrue(any(c["type"] == "assertion_changed" and c["binding"]["record_id"] == "use" for c in causes))
        self.assertEqual({c["upstream_binding"]["record_id"] for c in causes if c["type"] == "upstream_affected"}, {"left", "right"})
        self.assertEqual(self.view("join")["generation"], 2)
        self.assertEqual(len(self.view("join")["routes"][0]["premises"]), 2)
        self.assertEqual(len(self.view("join")["routes"]), 2)
        tail_causes = self.view("tail")["mechanical_freshness"]["last_transition"]["causes"]
        self.assertTrue(any(c["type"] == "assertion_changed" and c["binding"]["record_id"] == "use" for c in tail_causes))
        self.assertEqual({c["binding"]["record_id"] for c in tail_causes if c["type"] == "policy_changed"},
                         {"use", "left", "right", "join", "tail"})

    def test_typed_generic_decision_stays_forbidden(self):
        """Schema 5 does not turn opaque Decisions into supported typed content."""
        before = metadata(self.root)
        with self.assertRaises(DomainValidationError):
            self.store.submit_typed(batch("opaque", [policy_record()]))
        self.assertEqual(metadata(self.root), before)


if __name__ == "__main__":
    unittest.main()
