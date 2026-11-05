"""Setup-only synthetic acyclic two-route and downstream claim-use graph."""

from dataclasses import replace
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference, Submission
from research_pipeline.scientific import Claim, ResearchContext, Justification, Evidence, encode_envelope
from research_pipeline.assessment import (
    IndependenceDeclaration, SubstantiveAssessment, SupportRouteAssessment, Review, Issue,
    encode_envelope as assessment_envelope,
)
from research_pipeline.claim_use import ClaimUse, ClaimUsePremise, ClaimUseRoute, ClaimUseInspectionLimits
from research_pipeline.claim_use import encode_envelope as use_envelope

PROVENANCE = CreationProvenance("synthetic", "2026-11-05T00:00:00Z")
LIMITS = ClaimUseInspectionLimits(512, 1024, 8192, 1024, 64*1024*1024, 4*1024*1024)


def ref(identity, role, kind, revision=1):
    """Declare an exact target without suggesting authority or resolving it."""
    return RecordReference(identity, revision, role, kind)


def batch(identity, records, heads=None):
    """Build an ordinary attributed batch with explicit expected-head CAS."""
    return Submission(identity, PROVENANCE, records,
                      {r.record_id: r.revision-1 for r in records} if heads is None else heads)


def review(candidate="candidate", route="route-a", scope="scope"):
    """Report favorable synthetic scope without authenticating execution or sufficiency."""
    return Review(ref(candidate, "candidate_claim", "claim"), ref(scope, "target_context", "research_context"),
                  "synthetic reviewer", IndependenceDeclaration("candidate_aware_audit", "candidate_aware_audit",
                  [], [], [], [], [], [], []), ref("manifest", "context_manifest", "work_product_manifest"),
                  ref("policy", "authorization_policy", "decision"), [],
                  SubstantiveAssessment("under_review", "supported_within_scope", ["analytical"],
                  "applicable", "unassessed", "Attributed only", [], [], []),
                  [SupportRouteAssessment(ref(route, "assessed_route", "justification"),
                  "sufficient", "Unverified", [], [])], [], [], [], "synthetic")


def issue(affected="route-a", kind="justification"):
    """Declare an open blocking issue over an exact shallow association target."""
    return Issue("Synthetic objection", [ref(affected, "affected_record", kind)], "Unverified objection",
                 "blocking", "Inspect", "open", "Attributed only", [], [], [], "synthetic")


def binding(candidate="candidate", routes=("route-a", "route-b"), assessments=("review-a", "review-b"),
            premises=("premise-a", "premise-b"), upstream=None, issues=()):
    """Bind separate routes and complete conjunctions with explicit optional upstream pins."""
    return ClaimUse(ref(candidate, "candidate_claim", "claim"), ref("scope", "target_context", "research_context"),
                    [ClaimUseRoute(ref(route, "support_route", "justification"),
                    [ClaimUsePremise(ref(premise, "premise", "claim"),
                    None if upstream is None else ref(upstream, "premise_use", "promotion_eligibility"))],
                    [ref(assessment, "support_assessment", "review")])
                    for route, assessment, premise in zip(routes, assessments, premises)],
                    [ref(i, "relevant_issue", "issue") for i in issues],
                    [ref("policy", "authorization_policy", "decision")], [])


def populate(store, *, uses=True):
    """Store real exact declarations and an acyclic scientific graph with two alternatives."""
    store.submit(batch("declarations", [RecordEnvelope(identity, 1, kind, {}, PROVENANCE)
                 for identity, kind in (("manifest", "work_product_manifest"), ("policy", "decision"))]))
    context = ResearchContext("Synthetic scope", [], [], [], [], [], [], [], [], [], [])
    records = [encode_envelope("scope", 1, context, PROVENANCE),
               encode_envelope("other-scope", 1, replace(context, question="Independent scope"), PROVENANCE)]
    for identity in ("candidate", "premise-a", "premise-b", "downstream", "unrelated"):
        records.append(encode_envelope(identity, 1, Claim(identity, "synthetic", [],
                       ref("scope", "context", "research_context"), [], [], []), PROVENANCE))
    artifact = store.put_artifact(b"synthetic direct evidence")
    evidence = Evidence([artifact], ref("scope", "context", "research_context"), "Synthetic property",
                        [], "Synthetic method", [], [], [], "Unverified", [], [], "synthetic")
    records.append(encode_envelope("evidence", 1, evidence, PROVENANCE))
    for route, premise, candidate in (("route-a", "premise-a", "candidate"),
                                      ("route-b", "premise-b", "candidate"),
                                      ("route-d", "candidate", "downstream")):
        value = Justification(ref("scope", "context", "research_context"),
                              [ref(premise, "premise", "claim")], [], route,
                              [ref(candidate, "conclusion", "claim")],
                              [ref("evidence", "evidence", "evidence")], [])
        records.append(encode_envelope(route, 1, value, PROVENANCE))
    records.extend(assessment_envelope(identity, 1, value, PROVENANCE) for identity, value in (
        ("review-a", review()), ("review-b", review(route="route-b")),
        ("review-d", review("downstream", "route-d"))))
    store.submit_typed(batch("scientific", records))
    if uses:
        upstream = use_envelope("use", 1, binding(), PROVENANCE)
        downstream = use_envelope("downstream-use", 1,
                    binding("downstream", ("route-d",), ("review-d",), ("candidate",), "use"), PROVENANCE)
        independent = use_envelope("unrelated-use", 1,
                    binding("unrelated", (), (), ()), PROVENANCE)
        initial = batch("register", [downstream, independent, upstream])
        return artifact, initial, store.submit_typed(initial)
    return artifact


def target_context_graph(store):
    """Store disjoint target scopes, a conjunctive alternative and historical downstream pins.

    Candidate/route/premise/evidence contexts deliberately remain `scope`; only
    explicit ClaimUse target scopes establish the new identity watches. Returned
    requests and values are setup data, never expected freshness calculations.
    """
    artifact = populate(store, uses=False)
    scope = ResearchContext(question="Old target question", equations=["d2x/dt2 = -x"],
                            definitions=["x is displacement"], units=["time in seconds"],
                            conventions=["real coordinates"], mathematical_domains=["x in R"],
                            boundary_conditions=["periodic boundary"], initial_conditions=[],
                            parameter_regime=["weak coupling"], approximations=["linear order"],
                            limit_ordering=["volume before time"])
    records = [encode_envelope(identity, 1, replace(scope, question=identity), PROVENANCE)
               for identity in ("target-a", "target-b", "target-d", "target-i")]
    route = Justification(ref("scope", "context", "research_context"),
        [ref(p, "premise", "claim") for p in ("premise-a", "premise-b")], [], "Conjunction",
        [ref("candidate", "conclusion", "claim")], [ref("evidence", "evidence", "evidence")], [])
    records.append(encode_envelope("conjunction", 1, route, PROVENANCE))
    records.extend(assessment_envelope(identity, 1, review(candidate, route, context), PROVENANCE)
        for identity, candidate, route, context in (
            ("context-review-a", "candidate", "conjunction", "target-a"),
            ("context-review-alt", "candidate", "route-b", "target-a"),
            ("context-review-d", "downstream", "route-d", "target-d")))
    store.submit_typed(batch("target-science", records))
    upstream = replace(binding(), target_context=ref("target-a", "target_context", "research_context"),
        routes=[ClaimUseRoute(ref("conjunction", "support_route", "justification"),
            [ClaimUsePremise(ref(p, "premise", "claim"), None) for p in ("premise-a", "premise-b")],
            [ref("context-review-a", "support_assessment", "review")]),
            ClaimUseRoute(ref("route-b", "support_route", "justification"),
            [ClaimUsePremise(ref("premise-b", "premise", "claim"), None)],
            [ref("context-review-alt", "support_assessment", "review")])])
    downstream = replace(binding("downstream", ("route-d",), ("context-review-d",), ("candidate",), "use"),
                         target_context=ref("target-d", "target_context", "research_context"))
    independent = replace(binding("unrelated", (), (), ()),
                          target_context=ref("target-i", "target_context", "research_context"))
    request = batch("target-register", [use_envelope(i, 1, v, PROVENANCE) for i, v in
                    (("downstream-use", downstream), ("unrelated-use", independent), ("use", upstream))])
    return artifact, request, store.submit_typed(request), upstream, downstream, independent


def support_context_graph(store, *, uses=True, shared=False):
    """Store independently identifiable selected scopes, exact upstreams and excluded links.

    Setup uses the original declarations/artifact helper, then gives even unrelated
    candidates disjoint contexts. Shared mode deliberately repeats one scope across
    all four selected roles and both alternatives, retaining every occurrence.
    Returned values are setup data, never expected projection/cause calculations.
    """
    artifact = populate(store, uses=False)
    scopes = {role: "support-shared" if shared else "support-"+role for role in
              ("candidate", "route-a", "route-b", "premise-a", "premise-b", "evidence")}
    context_ids = {*scopes.values(), "support-target", "down-target", "independent-target",
                   "down-scope", "independent-scope", "excluded-input", "excluded-target", "excluded-route"}
    context = ResearchContext("Synthetic support scope", ["f(x)=x"], ["x is real"], [], [], ["R"], [], [], [], [], [])
    records = [encode_envelope(i, 1, replace(context, question=i), PROVENANCE) for i in sorted(context_ids)]
    for identity, scope in (("s-candidate", scopes["candidate"]), ("s-premise-a", scopes["premise-a"]),
                            ("s-premise-b", scopes["premise-b"]), ("s-down", "down-scope"),
                            ("s-independent", "independent-scope"), ("excluded-claim", "excluded-target")):
        records.append(encode_envelope(identity, 1, Claim(identity, "synthetic", [],
                       ref(scope, "context", "research_context"), [], [], []), PROVENANCE))
    evidence = Evidence([artifact], ref(scopes["evidence"], "context", "research_context"), "Synthetic property",
                        [ref("excluded-claim", "target_claim", "claim")], "Synthetic method",
                        [ref("excluded-input", "input_record", "research_context")], [], [], "Unverified", [], [], "synthetic")
    records.append(encode_envelope("s-evidence", 1, evidence, PROVENANCE))
    definitions = (("s-route-a", scopes["route-a"], ("s-premise-a", "s-premise-b"), "s-candidate", True),
                   ("s-route-b", scopes["route-b"], ("s-premise-b",), "s-candidate", True),
                   ("s-route-d", "down-scope", ("s-candidate",), "s-down", False),
                   ("s-unselected", "excluded-route", (), "s-candidate", False))
    for identity, scope, premises, candidate, selected_evidence in definitions:
        records.append(encode_envelope(identity, 1, Justification(ref(scope, "context", "research_context"),
            [ref(p, "premise", "claim") for p in premises], [], identity,
            [ref(candidate, "conclusion", "claim"), ref("excluded-claim", "conclusion", "claim")],
            [ref("s-evidence", "evidence", "evidence")] if selected_evidence else [], []), PROVENANCE))
    for identity, candidate, route, target in (("s-review-a", "s-candidate", "s-route-a", "support-target"),
            ("s-review-b", "s-candidate", "s-route-b", "support-target"),
            ("s-review-d", "s-down", "s-route-d", "down-target")):
        records.append(assessment_envelope(identity, 1, review(candidate, route, target), PROVENANCE))
    store.submit_typed(batch("support-science", records))
    upstream = replace(binding("s-candidate", (), (), ()),
        target_context=ref("support-target", "target_context", "research_context"),
        routes=[ClaimUseRoute(ref(route, "support_route", "justification"),
            [ClaimUsePremise(ref(p, "premise", "claim"), None) for p in premises],
            [ref(assessment, "support_assessment", "review")]) for route, premises, assessment in (
                ("s-route-a", ("s-premise-a", "s-premise-b"), "s-review-a"),
                ("s-route-b", ("s-premise-b",), "s-review-b"))])
    downstream = replace(binding("s-down", ("s-route-d",), ("s-review-d",), ("s-candidate",), "use"),
                         target_context=ref("down-target", "target_context", "research_context"))
    independent = replace(binding("s-independent", (), (), ()),
                          target_context=ref("independent-target", "target_context", "research_context"))
    request = batch("support-register", [use_envelope(i, 1, v, PROVENANCE) for i, v in
                    (("downstream-use", downstream), ("unrelated-use", independent), ("use", upstream))])
    receipt = store.submit_typed(request) if uses else None
    return dict(artifact=artifact, request=request, receipt=receipt, upstream=upstream,
                downstream=downstream, independent=independent, scopes=scopes)
