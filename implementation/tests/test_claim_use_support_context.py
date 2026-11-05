"""Schema-7 support occurrences, exact historical propagation and complete scope observations."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import claim_use_store as freshness
from research_pipeline.claim_use import ClaimUsePremise, ClaimUseRoute, encode_envelope as use_envelope
from research_pipeline.domain import RecordEnvelope
from research_pipeline.scientific import Claim, Justification, encode_envelope
from research_pipeline.store import RecordStore, ReferenceResolutionError
from tests.claim_use_fixtures import (support_context_graph, batch, ref, review, binding, issue,
                                     assessment_envelope, PROVENANCE, LIMITS)
from tests.test_claim_use_context import exact, context_record, context_cause
from tests.test_claim_use_store import metadata


# Independent literal selection oracle. In particular, shared Evidence and the
# complete second conjunct are retained again on the alternative route.
OCCURRENCES = (
    (0, "s-candidate", "claim", "candidate_claim", -1, -1, -1, "candidate"),
    (1, "s-route-a", "justification", "support_route", 0, -1, -1, "route-a"),
    (2, "s-premise-a", "claim", "premise", 0, 0, -1, "premise-a"),
    (3, "s-premise-b", "claim", "premise", 0, 1, -1, "premise-b"),
    (4, "s-evidence", "evidence", "evidence", 0, -1, 0, "evidence"),
    (5, "s-route-b", "justification", "support_route", 1, -1, -1, "route-b"),
    (6, "s-premise-b", "claim", "premise", 1, 0, -1, "premise-b"),
    (7, "s-evidence", "evidence", "evidence", 1, -1, 0, "evidence"),
)


def descriptor(occurrence, *, identity="use", revision=1):
    """Specify public provenance from the independent literal oracle, without product projections."""
    ordinal, source, kind, role, route, premise, evidence, _ = occurrence
    return dict(binding=exact(identity, revision, "promotion_eligibility"), occurrence_ordinal=ordinal,
                source=exact(source, kind=kind), source_role=role, route_ordinal=route,
                premise_ordinal=premise, evidence_ordinal=evidence)


def support_cause(occurrence, context, *, identity="use", revision=1, bound=1, previous=1, new=2):
    """Independently specify every direct support-change field including its three exact scopes."""
    return dict(type="support_context_changed", **descriptor(occurrence, identity=identity, revision=revision),
                bound_context=exact(context, bound), previous_context=exact(context, previous),
                new_context=exact(context, new))


class SupportContextTests(unittest.TestCase):
    """Real isolated stores exercise all four source roles and immutable upstream binding pins."""

    def setUp(self):
        """Create a private schema-7 store with independently identifiable support and unrelated scopes."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=7)
        self.addCleanup(self.store.close)
        self.fixture = support_context_graph(self.store)

    def view(self, identity="use"):
        """Read a detached complete version-4 inspection under all public maximum limits."""
        return self.store.inspect_claim_use(identity, limits=LIMITS).to_dict()

    def test_every_role_exact_effects_content_provenance_and_unchanged_claims(self):
        """Each selected role, including both conjuncts and repeated Evidence, advances precisely U and D."""
        original = self.view()
        before = metadata(self.root)
        for count, role in enumerate(("candidate", "route-a", "premise-a", "premise-b", "evidence", "route-b"), 2):
            context = "support-"+role
            method = self.store.submit if count % 2 else self.store.submit_typed
            method(batch("advance-"+role, [context_record(context)]))
            upstream, downstream = self.view(), self.view("downstream-use")
            expected = [support_cause(o, context) for o in OCCURRENCES if o[-1] == role]
            self.assertEqual(upstream["mechanical_freshness"]["last_transition"]["causes"],
                             sorted(expected, key=freshness._canonical))
            causes = downstream["mechanical_freshness"]["last_transition"]["causes"]
            if role == "candidate":
                own = (2, "s-candidate", "claim", "premise", 0, 0, -1, "candidate")
                expected.append(support_cause(own, context, identity="downstream-use"))
            expected.append(dict(type="upstream_affected", upstream_binding=exact("use", kind="promotion_eligibility")))
            self.assertEqual(causes, sorted(expected, key=freshness._canonical))
            self.assertEqual([upstream["generation"], downstream["generation"], self.view("unrelated-use")["generation"]],
                             [count, count, 1])
            self.assertEqual(upstream["binding"], original["binding"])
            self.assertEqual(len(upstream["routes"][0]["premises"]), 2)
            self.assertEqual(upstream["version"], 4)
            self.assertEqual(upstream["support_context_freshness"], dict(available=True, activation_event_watermark=0))
            observations = upstream["observed_support_contexts"]
            self.assertEqual(len(observations), 8)
            for occurrence, observation in zip(OCCURRENCES, observations):
                self.assertEqual({k: observation[k] for k in descriptor(occurrence)}, descriptor(occurrence))
                self.assertEqual(observation["bound_context"], exact("support-"+occurrence[-1]))
                self.assertEqual(observation["bound_content"], self.store.get_typed_revision("support-"+occurrence[-1], 1)[1].to_dict())
                self.assertTrue(observation["attributed"])
            self.assertEqual((upstream["eligible"], upstream["requires_reassessment"], upstream["authorized_disposition"]["available"]),
                             (False, True, False))
            self.assertTrue(any("Evidence s-evidence@1" in s and "route 1 evidence 0" in s for s in upstream["limitations"]))
        after = metadata(self.root)
        for table in ("claim_use_dependencies", "claim_use_support_contexts", "claim_use_bindings", "claim_use_upstreams"):
            self.assertEqual(after[table], before[table])
        self.assertEqual([r for r in after["revisions"] if not r[0].startswith("support-")],
                         [r for r in before["revisions"] if not r[0].startswith("support-")])

    def test_excluded_sources_and_first_creation_do_not_watch(self):
        """Evidence inputs/target claims, other conclusions, unselected routes and prose stay excluded."""
        before = [self.view(i)["generation"] for i in ("use", "downstream-use", "unrelated-use")]
        self.store.submit(batch("excluded", [context_record(i) for i in
            ("excluded-input", "excluded-target", "excluded-route", "scope", "other-scope")]+[
                context_record("brand-new", 1), RecordEnvelope("unrelated-event", 1, "event",
                    {"support_context": "support-candidate"}, PROVENANCE)]))
        self.assertEqual([self.view(i)["generation"] for i in ("use", "downstream-use", "unrelated-use")], before)
        self.store.submit(batch("generic-context", [RecordEnvelope("opaque-context", 1, "research_context", {}, PROVENANCE)]))
        self.store.submit(batch("generic-successor", [RecordEnvelope("opaque-context", 2, "research_context", {}, PROVENANCE)]))
        self.assertEqual(self.view()["generation"], before[0])

    def test_shared_context_occurrences_and_target_watch_remain_separate(self):
        """Eight shared occurrences and a coincident target keep their complete distinct identities."""
        with RecordStore.create(self.parent/"shared", schema_version=7) as store:
            fixture = support_context_graph(store, uses=False, shared=True)
            upstream = replace(fixture["upstream"], target_context=ref("support-shared", "target_context", "research_context"),
                routes=[replace(r, assessments=[ref("shared-review-"+str(i), "support_assessment", "review")])
                        for i, r in enumerate(fixture["upstream"].routes)])
            assessments = [assessment_envelope("shared-review-"+str(i), 1,
                review("s-candidate", r.justification.record_id, "support-shared"), PROVENANCE)
                for i, r in enumerate(upstream.routes)]
            store.submit_typed(batch("shared-register", [*assessments, use_envelope("use", 1, upstream, PROVENANCE)]))
            original = store.get_typed_revision("support-shared", 1)[1]
            store.submit(batch("identical", [encode_envelope("support-shared", 2, original, PROVENANCE)]))
            view = store.inspect_claim_use("use", limits=LIMITS).to_dict()
            expected = [support_cause(o, "support-shared") for o in OCCURRENCES]+[context_cause("use", "support-shared")]
            self.assertEqual(view["mechanical_freshness"]["last_transition"]["causes"], sorted(expected, key=freshness._canonical))
            self.assertEqual(len(view["observed_support_contexts"]), 8)
            self.assertEqual(len(view["observed_target_contexts"]), 1)
            self.assertTrue(all(o["superseded"] and o["bound_content"] == o["observed_content"] for o in view["observed_support_contexts"]))

    def test_historical_rebinding_disjoint_and_overlapping_replacements(self):
        """D follows U@1 after replacement; U@2 changes only for its own explicit selected scopes."""
        original = self.view()["binding"]
        replacement = self.fixture["independent"]
        self.store.submit_typed(batch("rebind-disjoint", [use_envelope("use", 2, replacement, PROVENANCE)]))
        self.assertEqual(self.view("downstream-use")["generation"], 1)
        self.store.submit(batch("old-evidence", [context_record("support-evidence")]))
        self.assertEqual([self.view(i)["generation"] for i in ("use", "downstream-use")], [2, 2])
        downstream = self.view("downstream-use")
        self.assertEqual(downstream["upstream_bindings"][0], original)
        self.assertTrue(any(o["source_role"] == "evidence" and o["superseded"] for o in downstream["observed_support_contexts"]))
        overlap = replace(replacement, candidate_claim=self.fixture["upstream"].candidate_claim)
        self.store.submit_typed(batch("rebind-overlap", [use_envelope("use", 3, overlap, PROVENANCE)]))
        self.store.submit(batch("old-candidate", [context_record("support-candidate")]))
        self.assertEqual([self.view(i)["generation"] for i in ("use", "downstream-use")], [4, 3])
        expected = support_cause(OCCURRENCES[0], "support-candidate", revision=3)
        self.assertEqual(self.view()["mechanical_freshness"]["last_transition"]["causes"], [expected])
        self.assertEqual(self.view("downstream-use")["upstream_bindings"][0], original)

    def test_old_pin_registration_and_same_batch_forward_pins(self):
        """Supersession is derived without an invented transition; forward old/new pins coalesce once."""
        self.store.submit(batch("already-advanced", [context_record("support-candidate")]))
        value = replace(self.fixture["upstream"], routes=[])
        self.store.submit_typed(batch("late", [use_envelope("late", 1, value, PROVENANCE)]))
        view = self.view("late")
        self.assertEqual([c["type"] for c in view["mechanical_freshness"]["last_transition"]["causes"]], ["binding_registered"])
        self.assertTrue(view["observed_support_contexts"][0]["superseded"])
        self.assertIn("support_context_pin_superseded", {c["type"] for c in view["mechanical_freshness"]["reasons"]})
        new_claim = encode_envelope("new-candidate", 1, Claim("new", "synthetic", [],
            ref("support-candidate", "context", "research_context", 3), [], [], []), PROVENANCE)
        forward = replace(value, candidate_claim=ref("new-candidate", "candidate_claim", "claim"))
        request = batch("forward", [use_envelope("new-pin", 1, forward, PROVENANCE),
            use_envelope("old-pin", 1, value, PROVENANCE), new_claim, context_record("support-candidate", 3)])
        original, prospective = freshness._inspection, {}
        def capture(reader, identity, limits):
            """Capture real prospective output, preserving all checks and finite accounting."""
            result = original(reader, identity, limits)
            if reader.overlay is not None:
                prospective[identity] = result.to_dict()
            return result
        with patch.object(freshness, "_inspection", capture):
            self.store.submit(request)
        for identity, expected in prospective.items():
            actual = self.view(identity)
            expected["mechanical_freshness"]["last_transition"]["event_id"] = actual["mechanical_freshness"]["last_transition"]["event_id"]
            self.assertEqual(actual, expected)
        for identity, bound in (("old-pin", 1), ("new-pin", 3)):
            view = self.view(identity)
            self.assertEqual(view["generation"], 1)
            cause = next(c for c in view["mechanical_freshness"]["last_transition"]["causes"] if c["type"] == "support_context_changed")
            self.assertEqual(cause["bound_context"], exact("support-candidate", bound))
            self.assertEqual(cause["previous_context"], exact("support-candidate", 2))
            self.assertEqual(view["observed_support_contexts"][0]["superseded"], bound == 1)

    def test_mixed_changes_coalesce_all_origins_and_rebinding(self):
        """Support, target, policy, Review, Issue and binding registration share final-current generations."""
        self.store.submit(batch("mixed", [context_record("support-evidence"), context_record("support-target"),
            RecordEnvelope("policy", 2, "decision", {}, PROVENANCE),
            assessment_envelope("s-review-a", 2, replace(review("s-candidate", "s-route-a", "support-target"), reviewer="Changed"), PROVENANCE),
            assessment_envelope("direct", 1, issue("use", "promotion_eligibility"), PROVENANCE),
            use_envelope("use", 2, self.fixture["upstream"], PROVENANCE)]))
        for identity in ("use", "downstream-use"):
            view = self.view(identity)
            self.assertEqual(view["generation"], 2)
            self.assertTrue({"support_context_changed", "target_context_changed", "policy_changed", "assertion_changed"}
                            <= {c["type"] for c in view["mechanical_freshness"]["last_transition"]["causes"]})
        self.assertEqual(self.view("unrelated-use")["generation"], 2)  # Its policy also advanced.
        support = [c for c in self.view()["mechanical_freshness"]["last_transition"]["causes"] if c["type"] == "support_context_changed"]
        self.assertEqual(support, sorted([support_cause(o, "support-evidence", revision=2) for o in (OCCURRENCES[4], OCCURRENCES[7])], key=freshness._canonical))

    def test_unequal_diamond_late_origins_repeated_edges_and_multiple_contexts(self):
        """All distinct origins survive unequal arrival lengths without path enumeration or lost deltas."""
        definitions = (("right", (("s-candidate", "use"),)), ("mid", (("s-down", "downstream-use"),)),
                       ("join", (("mid-claim", "mid"), ("right-claim", "right"))),
                       ("tail", (("join-claim", "join"),)))
        science, uses = [], []
        for identity, premises in definitions:
            candidate = identity+"-claim"
            scope = identity+"-scope"
            science.extend([context_record(scope, 1), encode_envelope(candidate, 1,
                Claim(candidate, "synthetic", [], ref(scope, "context", "research_context"), [], [], []), PROVENANCE)])
            routes = []
            for suffix, entries in (("", premises), ("-alt", premises[:1])) if identity == "join" else (("", premises),):
                route = identity+"-route"+suffix
                science.extend([encode_envelope(route, 1, Justification(ref(scope, "context", "research_context"),
                    [ref(c, "premise", "claim") for c, _ in entries], [], route,
                    [ref(candidate, "conclusion", "claim")], [], []), PROVENANCE),
                    assessment_envelope(route+"-review", 1, review(candidate, route, scope), PROVENANCE)])
                routes.append(ClaimUseRoute(ref(route, "support_route", "justification"),
                    [ClaimUsePremise(ref(c, "premise", "claim"), ref(u, "premise_use", "promotion_eligibility")) for c, u in entries],
                    [ref(route+"-review", "support_assessment", "review")]))
            uses.append(use_envelope(identity, 1, replace(binding(candidate, (), (), ()),
                target_context=ref(scope, "target_context", "research_context"), routes=routes), PROVENANCE))
        self.store.submit_typed(batch("diamond-science", science))
        self.store.submit_typed(batch("diamond-register", list(reversed(uses))))
        self.store.submit(batch("two-origins", [context_record("support-evidence"), context_record("support-premise-a")]))
        expected = [support_cause(o, "support-"+o[-1]) for o in (OCCURRENCES[2], OCCURRENCES[4], OCCURRENCES[7])]
        for identity, immediate in (("join", {"mid", "right"}), ("tail", {"join"})):
            view = self.view(identity)
            causes = view["mechanical_freshness"]["last_transition"]["causes"]
            self.assertEqual([c for c in causes if c["type"] == "support_context_changed"], sorted(expected, key=freshness._canonical))
            self.assertEqual({c["upstream_binding"]["record_id"] for c in causes if c["type"] == "upstream_affected"}, immediate)
            self.assertEqual(view["generation"], 2)

    def test_support_cycle_and_ancestral_candidate_rejections_rollback(self):
        """New context watches do not relax exact support graph rules or change association cycles."""
        bad = replace(self.fixture["downstream"], routes=[replace(self.fixture["downstream"].routes[0],
            premises=[ClaimUsePremise(ref("s-candidate", "premise", "claim"), ref("cycle", "premise_use", "promotion_eligibility"))])])
        before = metadata(self.root)
        with self.assertRaises(ReferenceResolutionError):
            self.store.submit_typed(batch("cycle", [use_envelope("cycle", 1, bad, PROVENANCE)]))
        self.assertEqual(metadata(self.root), before)
        # An Issue association cycle remains a bounded navigation graph, never support.
        self.store.submit(batch("association-cycle", [assessment_envelope("issue-a", 1, issue("issue-b", "issue"), PROVENANCE),
            assessment_envelope("issue-b", 1, issue("issue-a", "issue"), PROVENANCE)]))
        self.assertEqual(self.view()["generation"], 1)
