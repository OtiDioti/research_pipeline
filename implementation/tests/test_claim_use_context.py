"""Schema-6 target-context origins, immutable scope observations and exact historical impact."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import claim_use_store as freshness
from research_pipeline.claim_use import ClaimUsePremise, ClaimUseRoute, encode_envelope as use_envelope
from research_pipeline.domain import RecordEnvelope
from research_pipeline.scientific import Claim, ResearchContext, Justification, encode_envelope
from research_pipeline.store import RecordStore
from tests.claim_use_fixtures import (
    target_context_graph, populate, binding, batch, ref, review, issue,
    assessment_envelope, PROVENANCE, LIMITS,
)
from tests.test_claim_use_store import metadata


def exact(identity, revision=1, kind="research_context"):
    """State an independently specified public exact pin, without using production helpers."""
    return dict(record_id=identity, revision=revision, target_kind=kind)


def context_record(identity="target-a", revision=2, question="Prose-only successor"):
    """Create a coherent scientific scope; repeated questions allow identical successors."""
    value = ResearchContext(question=question, equations=["d2x/dt2 = -x"],
                            definitions=["x is displacement"], units=["time in seconds"],
                            conventions=["real coordinates"], mathematical_domains=["x in R"],
                            boundary_conditions=["periodic boundary"], initial_conditions=[],
                            parameter_regime=["weak coupling"], approximations=["linear order"],
                            limit_ordering=["volume before time"])
    return encode_envelope(identity, revision, value, PROVENANCE)


def context_cause(binding_id, context_id="target-a", *, binding_revision=1, bound=1, previous=1, new=2):
    """Specify every direct context cause field independently of stored projections."""
    return dict(type="target_context_changed", binding=exact(binding_id, binding_revision, "promotion_eligibility"),
                dependency_ordinal=1, bound_context=exact(context_id, bound),
                previous_context=exact(context_id, previous), new_context=exact(context_id, new))


class TargetContextTests(unittest.TestCase):
    """Public generic/typed writes retain precise scope and conservative negative authorization."""

    def setUp(self):
        """Own disposable real SQLite state and separate explicit target contexts per test."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=6)
        self.addCleanup(self.store.close)
        self.artifact, self.initial, self.receipt, self.upstream, self.downstream, self.independent = target_context_graph(self.store)

    def view(self, identity="use"):
        """Read one complete public coherent metadata-only version-3 view."""
        return self.store.inspect_claim_use(identity, limits=LIMITS).to_dict()

    def test_prose_and_identical_successors_exact_generations_causes_and_scopes(self):
        """All successors matter, while candidate statements and immutable historical scope remain exact."""
        original = self.view()
        before = metadata(self.root)
        for revision, method in ((2, self.store.submit), (3, self.store.submit_typed)):
            receipt = method(batch(f"context-{revision}", [context_record(revision=revision)]))
            upstream, downstream = self.view(), self.view("downstream-use")
            cause = context_cause("use", previous=revision-1, new=revision)
            self.assertEqual(upstream["generation"], revision)
            self.assertEqual(downstream["generation"], revision)
            self.assertEqual(self.view("unrelated-use")["generation"], 1)
            self.assertEqual(upstream["mechanical_freshness"]["last_transition"]["causes"], [cause])
            self.assertEqual(downstream["mechanical_freshness"]["last_transition"]["causes"], sorted([
                cause, dict(type="upstream_affected", upstream_binding=exact("use", kind="promotion_eligibility"))],
                key=lambda c: freshness._canonical(c)))
            self.assertEqual(upstream["mechanical_freshness"]["last_transition"]["event_id"], receipt.event_id)
            occurrence = upstream["observed_target_contexts"][0]
            self.assertEqual(occurrence, dict(binding=exact("use", kind="promotion_eligibility"),
                dependency_ordinal=1, bound_context=exact("target-a"), observed_context=exact("target-a", revision),
                bound_content=original["observed_target_contexts"][0]["bound_content"],
                observed_content=self.store.get_typed_revision("target-a", revision)[1].to_dict(),
                attributed=True, superseded=True))
            self.assertIn(dict(type="target_context_pin_superseded", **{k: occurrence[k] for k in
                ("binding", "dependency_ordinal", "bound_context", "observed_context")}), upstream["mechanical_freshness"]["reasons"])
            self.assertEqual(upstream["binding"], original["binding"])
            self.assertEqual((upstream["eligible"], upstream["requires_reassessment"], upstream["authorized_disposition"]),
                             (False, True, dict(available=False, eligible=False)))
            self.assertEqual(len(upstream["routes"]), 2)
            self.assertEqual(len(upstream["routes"][0]["premises"]), 2)
            self.assertTrue(any("Unresolved context transfer" in reason for reason in upstream["limitations"]))
        after = metadata(self.root)
        for table in ("claim_use_bindings", "claim_use_dependencies", "claim_use_upstreams", "artifact_links", "artifacts"):
            self.assertEqual(after[table], before[table])
        for table in ("revisions", "record_links"):
            self.assertEqual([r for r in after[table] if r[0] != "target-a"], [r for r in before[table] if r[0] != "target-a"])

    def test_exact_version_three_contract_and_history_stays_version_one(self):
        """Version 3 adds exactly two fields and preserves original transition history values."""
        view = self.view()
        expected_fields = {"format", "version", "use_id", "binding_revision", "generation", "status",
            "requires_reassessment", "eligible", "mechanical_freshness", "authorized_disposition", "binding",
            "candidate", "context", "routes", "historical_pins", "upstream_bindings", "observed_assertions",
            "limitations", "attachment_availability", "observed_policies", "policy_freshness",
            "observed_target_contexts", "target_context_freshness"}
        self.assertEqual(set(view), expected_fields)
        self.assertEqual(view["version"], 3)
        self.assertEqual(view["target_context_freshness"], dict(available=True, activation_event_watermark=0))
        self.assertEqual(view["context"], ref("target-a", "target_context", "research_context").to_dict())
        history = self.store.claim_use_history("use", limits=LIMITS).to_dict()
        self.assertEqual(history["version"], 1)
        self.assertEqual(history["transitions"], [view["mechanical_freshness"]["last_transition"]])
        self.assertFalse(view["observed_target_contexts"][0]["superseded"])
        self.assertTrue(all(a["attributed"] for a in view["observed_assertions"]))

    def test_only_explicit_target_contexts_watch_successors(self):
        """Candidate/route/premise/evidence/Review/Issue mentions and generic bindings create no watch."""
        self.store.submit(batch("generic-context", [RecordEnvelope("opaque-context", 1, "research_context", {}, PROVENANCE)]))
        generic = RecordEnvelope("unregistered", 1, "promotion_eligibility", {"target_context": "opaque-context"},
                                 PROVENANCE, [ref("opaque-context", "target_context", "research_context")])
        self.store.submit(batch("unregistered", [generic]))
        self.store.submit_typed(batch("mention", [assessment_envelope("context-issue", 1,
            issue("other-scope", "research_context"), PROVENANCE)]))
        generations = {i: self.view(i)["generation"] for i in ("use", "downstream-use", "unrelated-use")}
        self.store.submit(batch("unwatched-contexts", [context_record("scope"), context_record("other-scope"),
            context_record("target-b"), RecordEnvelope("opaque-context", 2, "research_context", {"unsupported": True}, PROVENANCE)]))
        self.assertEqual({i: self.view(i)["generation"] for i in generations}, generations)
        self.store.submit(batch("global-event", [RecordEnvelope("global", 1, "event", {"target-a": "changed"}, PROVENANCE)]))
        self.assertEqual(self.view()["generation"], generations["use"])

    def test_historical_rebinding_never_redirects_downstream_context(self):
        """D pinning U@1/A follows A after current U@2/B; B affects only U@2's dependencies."""
        rebound = replace(binding("candidate", (), (), ()), target_context=ref("target-b", "target_context", "research_context"))
        self.store.submit_typed(batch("rebind", [use_envelope("use", 2, rebound, PROVENANCE)]))
        self.assertEqual(self.view("downstream-use")["generation"], 1)
        self.store.submit(batch("a2", [context_record()]))
        self.assertEqual([self.view(i)["generation"] for i in ("use", "downstream-use", "unrelated-use")], [2, 2, 1])
        downstream = self.view("downstream-use")
        self.assertEqual(downstream["upstream_bindings"][0]["binding"], exact("use", kind="promotion_eligibility"))
        self.assertEqual([o["bound_context"] for o in downstream["observed_target_contexts"]],
                         [exact("target-d"), exact("target-a")])
        self.assertIn(context_cause("use"), downstream["mechanical_freshness"]["last_transition"]["causes"])
        self.store.submit_typed(batch("b2", [context_record("target-b")]))
        self.assertEqual([self.view(i)["generation"] for i in ("use", "downstream-use")], [3, 2])
        self.assertEqual(self.view()["mechanical_freshness"]["last_transition"]["causes"],
                         [context_cause("use", "target-b", binding_revision=2)])

    def test_advanced_registration_same_batch_old_new_pins_and_first_creation(self):
        """Advanced heads derive observations; same-batch successor origins coalesce at generation one."""
        self.store.submit(batch("a2", [context_record()]))
        leaf = replace(binding("unrelated", (), (), ()), target_context=ref("target-a", "target_context", "research_context"))
        self.store.submit_typed(batch("late", [use_envelope("late", 1, leaf, PROVENANCE)]))
        self.assertEqual(self.view("late")["generation"], 1)
        self.assertTrue(self.view("late")["observed_target_contexts"][0]["superseded"])
        self.assertEqual([c["type"] for c in self.view("late")["mechanical_freshness"]["last_transition"]["causes"]], ["binding_registered"])
        new_pin = replace(leaf, target_context=ref("target-a", "target_context", "research_context", 3))
        first = replace(leaf, target_context=ref("fresh-context", "target_context", "research_context"))
        self.store.submit(batch("same-batch", [use_envelope("old-pin", 1, leaf, PROVENANCE),
            use_envelope("late", 2, new_pin, PROVENANCE), context_record(revision=3),
            use_envelope("first", 1, first, PROVENANCE), context_record("fresh-context", 1)]))
        for identity, revision, generation in (("old-pin", 1, 1), ("late", 3, 2)):
            view = self.view(identity)
            self.assertEqual(view["generation"], generation)
            self.assertIn(context_cause(identity, binding_revision=2 if identity == "late" else 1,
                bound=revision, previous=2, new=3), view["mechanical_freshness"]["last_transition"]["causes"])
        self.assertEqual([c["type"] for c in self.view("first")["mechanical_freshness"]["last_transition"]["causes"]], ["binding_registered"])

    def test_forward_registrations_prospective_views_equal_committed(self):
        """Forward support registrations and proposed observed heads appear before any insertion."""
        downstream = replace(self.downstream, routes=[replace(self.downstream.routes[0], premises=[
            replace(self.downstream.routes[0].premises[0], upstream_use=ref("forward", "premise_use", "promotion_eligibility"))])])
        request = batch("forward", [use_envelope("forward-down", 1, downstream, PROVENANCE),
            use_envelope("forward", 1, self.upstream, PROVENANCE), context_record(), context_record("target-d")])
        original, prospective = freshness._inspection, {}
        def capture(reader, identity, limits):
            """Record real maximum-limit prospective output without substituting calculations."""
            result = original(reader, identity, limits)
            if reader.overlay is not None:
                prospective[identity] = result.to_dict()
            return result
        with patch.object(freshness, "_inspection", capture):
            self.store.submit(request)
        self.assertEqual(set(prospective), {"use", "downstream-use", "forward", "forward-down"})
        for identity, expected in prospective.items():
            persisted = self.view(identity)
            expected["mechanical_freshness"]["last_transition"]["event_id"] = persisted["mechanical_freshness"]["last_transition"]["event_id"]
            self.assertEqual(expected, persisted)

    def test_mixed_review_issue_policy_context_and_rebinding_one_transition(self):
        """All distinct origins share one final-current transition, with historical effects on D."""
        request = batch("mixed", [context_record(),
            RecordEnvelope("policy", 2, "decision", {"prose": "changed"}, PROVENANCE),
            assessment_envelope("context-review-a", 2, replace(review("candidate", "conjunction", "target-a"),
                reviewer="Revised prose"), PROVENANCE),
            assessment_envelope("direct", 1, issue("use", "promotion_eligibility"), PROVENANCE),
            use_envelope("use", 2, self.upstream, PROVENANCE)])
        self.store.submit(request)
        for identity in ("use", "downstream-use"):
            view = self.view(identity)
            self.assertEqual(view["generation"], 2)
            self.assertEqual(len(self.store.claim_use_history(identity, limits=LIMITS).to_dict()["transitions"]), 2)
            causes = view["mechanical_freshness"]["last_transition"]["causes"]
            self.assertTrue({"target_context_changed", "policy_changed", "assertion_changed"} <= {c["type"] for c in causes})
        self.assertIn(context_cause("use", binding_revision=2), self.view()["mechanical_freshness"]["last_transition"]["causes"])
        self.assertEqual(self.view("unrelated-use")["generation"], 2)  # Its own policy changed.

    def test_mixed_final_binding_retains_complete_independent_cause_set(self):
        """Specify all mixed origins for a minimal binding without deriving the oracle from indexes."""
        leaf = replace(binding("unrelated", (), (), ()),
                       target_context=ref("target-a", "target_context", "research_context"))
        assessment = replace(review("unrelated", scope="target-a"), route_assessments=[])
        self.store.submit_typed(batch("leaf-setup", [use_envelope("leaf", 1, leaf, PROVENANCE),
            assessment_envelope("leaf-review", 1, assessment, PROVENANCE)]))
        self.store.submit(batch("leaf-mixed", [context_record(),
            RecordEnvelope("policy", 2, "decision", {"prose": "successor"}, PROVENANCE),
            assessment_envelope("leaf-review", 2, replace(assessment, reviewer="Second reviewer"), PROVENANCE),
            assessment_envelope("leaf-issue", 1, issue("unrelated", "claim"), PROVENANCE),
            use_envelope("leaf", 2, leaf, PROVENANCE)]))
        binding_pin = exact("leaf", 2, "promotion_eligibility")
        expected = [dict(type="binding_registered", binding=binding_pin),
                    context_cause("leaf", binding_revision=2),
                    dict(type="policy_changed", binding=binding_pin, dependency_ordinal=2,
                         bound_policy=exact("policy", kind="decision"),
                         previous_policy=exact("policy", kind="decision"),
                         new_policy=exact("policy", 2, "decision"))]
        # This binding declares candidate, context and policy in that exact order;
        # both assertions affect its candidate occurrence, with no route occurrences.
        for identity, revision, kind in (("leaf-review", 2, "review"), ("leaf-issue", 1, "issue")):
            expected.append(dict(type="assertion_changed", binding=binding_pin,
                assertion=exact(identity, revision, kind), dependency=dict(ordinal=0,
                    target=exact("unrelated", kind="claim"), role="candidate",
                    context=exact("target-a"), route_ordinal=-1, premise_ordinal=-1)))
        view = self.view("leaf")
        self.assertEqual(view["generation"], 2)
        self.assertEqual(view["mechanical_freshness"]["last_transition"]["causes"],
                         sorted(expected, key=freshness._canonical))
        self.assertEqual(len(self.store.claim_use_history("leaf", limits=LIMITS).to_dict()["transitions"]), 2)

    def test_multiple_context_origins_survive_unequal_diamond_and_immediate_reasons(self):
        """Late origins traverse a longer branch without losing exact conjunction/alternative structure."""
        # U→D→mid→join and U→right→join produce unequal arrival lengths.
        definitions = (("right", "unrelated", (("candidate", "use"),)),
                       ("mid", "mid-claim", (("downstream", "downstream-use"),)),
                       ("join", "joined", (("mid-claim", "mid"), ("unrelated", "right"))),
                       ("tail", "tail-claim", (("joined", "join"),)))
        science, values = [], []
        for identity, candidate, premises in definitions:
            scope = identity+"-context"
            science.append(context_record(scope, 1))
            if candidate != "unrelated":
                science.append(encode_envelope(candidate, 1, Claim(candidate, "synthetic", [],
                    ref("scope", "context", "research_context"), [], [], []), PROVENANCE))
            routes = []
            for suffix, entries in (("", premises), ("-alt", premises[:1])) if identity == "join" else (("", premises),):
                route = identity+"-route"+suffix
                science.extend([encode_envelope(route, 1, Justification(ref("scope", "context", "research_context"),
                    [ref(c, "premise", "claim") for c, u in entries], [], route,
                    [ref(candidate, "conclusion", "claim")], [], []), PROVENANCE),
                    assessment_envelope(route+"-review", 1, review(candidate, route, scope), PROVENANCE)])
                routes.append(ClaimUseRoute(ref(route, "support_route", "justification"),
                    [ClaimUsePremise(ref(c, "premise", "claim"), ref(u, "premise_use", "promotion_eligibility")) for c, u in entries],
                    [ref(route+"-review", "support_assessment", "review")]))
            values.append(use_envelope(identity, 1, replace(binding(candidate, (), (), ()),
                target_context=ref(scope, "target_context", "research_context"), routes=routes), PROVENANCE))
        self.store.submit_typed(batch("diamond-science", science))
        self.store.submit_typed(batch("diamond", list(reversed(values))))
        self.store.submit(batch("origins", [context_record(), context_record("target-d")]))
        expected_origins = [context_cause("use"), context_cause("downstream-use", "target-d")]
        for identity, immediate in (("join", {"mid", "right"}), ("tail", {"join"})):
            view = self.view(identity)
            causes = view["mechanical_freshness"]["last_transition"]["causes"]
            self.assertEqual([c for c in causes if c["type"] == "target_context_changed"], sorted(expected_origins, key=freshness._canonical))
            self.assertEqual({c["upstream_binding"]["record_id"] for c in causes if c["type"] == "upstream_affected"}, immediate)
            self.assertEqual(view["generation"], 2)
        self.assertEqual(len(self.view("join")["routes"][0]["premises"]), 2)
        self.assertEqual(len(self.view("join")["routes"]), 2)


if __name__ == "__main__":
    unittest.main()
