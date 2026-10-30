"""Load a synthetic paper example; validate its contract, never scientific truth."""

import json
from pathlib import Path


class FixtureValidationError(ValueError):
    """An input is malformed JSON or violates the synthetic oscillator contract."""


_ORACLE = "Expected fixture oracle, not observed execution or expert judgment."
_PROVENANCE = {
    "synthetic": True, "classification": "synthetic-development",
    "expert_audited": False, "held_out": False, "simulation": True,
    "execution": "not_performed", "oracle_statement": _ORACLE,
}
_COMMON = {"id", "revision", "kind", "simulated_role", *_PROVENANCE}
_FIELDS = {
    "seed": "question context readiness",
    "context": "scope coefficient_signs domain observable hamiltonian parameters units small_parameter boundary_assumptions projection existence_is_obligation",
    "obligation": "context category status requirement",
    "candidate": "context derived_from statement disposition review_status endorsement justifications support_use obligations frozen",
    "justification": "context method scope explanation evidence",
    "evidence": "context purpose scope expected_outcome target argument explanation",
    "task": "context justification evidence expected_outcome scope completion_condition",
    "review": "target context evidence argument expected_outcome refuted_scope preserved_scopes independence all_authored_together assessment",
    "issue": "target context review evidence argument disposition explanation",
    "snapshot": "stage task candidate context review issue evidence historical_candidate retained_obligations outstanding_obligations operational_status work_stage scientific_disposition applicability novelty endorsement support rationale",
    "proposed_question": "derived_from status observable boundary_conditions context_requirement task_requirement question",
    "partial_report": "snapshot historical_candidate contexts evidence justifications review issue task pending_candidate followup obligations stop_reason retained_results failed_interpretation pending_review next_action resources",
}
_ROLES = {
    "seed": "simulated_requester", "context": "simulated_framer",
    "obligation": "simulated_framer", "candidate": "simulated_explorer",
    "justification": "simulated_explorer", "evidence": "simulated_checker",
    "task": "simulated_executor", "review": "simulated_reviewer",
    "issue": "simulated_reviewer", "snapshot": "simulated_coordinator",
    "proposed_question": "simulated_explorer", "partial_report": "simulated_reporter",
}
_STAGES = ("baseline", "frozen", "challenged", "partial_stop")


def _require(condition, location, reason):
    """Raise a located contract error if a structural or scenario invariant fails."""
    if not condition:
        raise FixtureValidationError(f"{location}: {reason}")


def _fields(value, fields, location):
    """Require an ordinary JSON object with exactly the named contract fields."""
    _require(type(value) is dict, location, "expected object")
    _require(set(value) == set(fields), location,
             f"fields mismatch; missing={sorted(set(fields) - set(value))}, "
             f"unknown={sorted(set(value) - set(fields), key=str)}")


def _equal(value, expected, location):
    """Compare a fixed contract value without Python's boolean/integer equivalence."""
    _require(type(value) is type(expected) and value == expected, location,
             f"expected {expected!r}")


def _text(value, location):
    """Require substantive explanatory prose without judging its scientific content."""
    _require(type(value) is str and len(value.strip()) >= 20, location,
             "expected substantive text (at least 20 characters)")


def _choice(value, choices, location):
    """Require a string drawn from the example's finite vocabulary."""
    _require(type(value) is str and value in choices, location,
             f"expected one of {tuple(choices)!r}")


def _reference(value, index, kinds, location, optional=False):
    """Resolve an exact typed reference; never infer the latest revision."""
    if optional and value is None:
        return None
    _fields(value, {"id", "revision"}, location)
    _require(type(value["id"]) is str and bool(value["id"].strip()), location, "invalid id")
    _require(type(value["revision"]) is int and value["revision"] > 0,
             location, "revision must be a positive integer")
    key = (value["id"], value["revision"])
    _require(key in index, location, f"dangling exact reference {key!r}")
    record = index[key]
    _require(record["kind"] in kinds, location, f"reference requires kind {kinds!r}")
    return record


def _references(value, index, kinds, location):
    """Resolve a nonempty, duplicate-free list of exact typed references."""
    _require(type(value) is list and bool(value), location, "expected nonempty reference list")
    records = [_reference(item, index, kinds, f"{location}[{i}]") for i, item in enumerate(value)]
    keys = [(r["id"], r["revision"]) for r in records]
    _require(len(set(keys)) == len(keys), location, "duplicate references")
    return records


def _ref(record):
    """Return the exact identity of a record for relationship comparisons."""
    return {"id": record["id"], "revision": record["revision"]}


def _same_refs(value, records, location):
    """Require exact scenario links in their declared order, preserving history."""
    _equal(value, [_ref(record) for record in records], location)


def _validate_record(record, index, location):
    """Validate kind-specific fields and typed links before scenario reconciliation."""
    kind = record["kind"]
    for name, expected in _PROVENANCE.items():
        _equal(record[name], expected, f"{location}.{name}")
    _equal(record["simulated_role"], _ROLES[kind], f"{location}.simulated_role")
    # Reference schemas remain local to this one example, not a generic graph API.
    single = {
        "seed": {"context": "context"},
        "obligation": {"context": "context"},
        "candidate": {"context": "context", "derived_from": "candidate"},
        "justification": {"context": "context"},
        "evidence": {"context": "context", "target": "candidate", "argument": "justification"},
        "task": {"context": "context", "justification": "justification"},
        "review": {"target": "candidate", "context": "context", "argument": "justification"},
        "issue": {"target": "candidate", "context": "context", "review": "review", "argument": "justification"},
        "snapshot": {"task": "task", "candidate": "candidate", "context": "context", "review": "review", "issue": "issue", "historical_candidate": "candidate"},
        "proposed_question": {"derived_from": "candidate"},
        "partial_report": {"snapshot": "snapshot", "historical_candidate": "candidate", "review": "review", "issue": "issue", "task": "task", "pending_candidate": "candidate", "followup": "proposed_question"},
    }
    multiple = {
        "candidate": {"justifications": "justification", "obligations": "obligation"},
        "justification": {"evidence": "evidence"}, "task": {"evidence": "evidence"},
        "review": {"evidence": "evidence"}, "issue": {"evidence": "evidence"},
        "snapshot": {"evidence": "evidence", "retained_obligations": "obligation", "outstanding_obligations": "obligation"},
        "partial_report": {"contexts": "context", "evidence": "evidence", "justifications": "justification", "obligations": "obligation"},
    }
    nullable = {("candidate", "derived_from"), ("evidence", "target"), ("evidence", "argument"),
                ("snapshot", "candidate"), ("snapshot", "review"), ("snapshot", "issue"),
                ("snapshot", "historical_candidate")}
    for field, target_kind in single.get(kind, {}).items():
        _reference(record[field], index, (target_kind,), f"{location}.{field}",
                   (kind, field) in nullable)
    for field, target_kind in multiple.get(kind, {}).items():
        _references(record[field], index, (target_kind,), f"{location}.{field}")
    prose = {
        "seed": "question", "context": "hamiltonian parameters units small_parameter boundary_assumptions projection",
        "obligation": "requirement", "candidate": "statement", "justification": "explanation",
        "evidence": "explanation", "task": "completion_condition", "review": "assessment",
        "issue": "explanation", "snapshot": "rationale",
        "proposed_question": "observable boundary_conditions context_requirement task_requirement question",
        "partial_report": "retained_results failed_interpretation next_action",
    }
    for field in prose[kind].split():
        _text(record[field], f"{location}.{field}")
    if kind == "seed":
        _equal(record["readiness"], "simulated_ready", location + ".readiness")
    elif kind == "context":
        _choice(record["scope"], ("both_signs", "positive"), location + ".scope")
        _equal(record["coefficient_signs"], ["positive", "negative"] if record["scope"] == "both_signs" else ["positive"], location + ".coefficient_signs")
        _equal(record["domain"], "full_real_line", location + ".domain")
        _equal(record["observable"], "minimum_energy_ground_state", location + ".observable")
        _equal(record["existence_is_obligation"], True, location + ".existence_is_obligation")
    elif kind == "obligation":
        _choice(record["category"], ("existence_domain", "approximation", "convergence"), location + ".category")
        _equal(record["status"], "unresolved", location + ".status")
    elif kind == "candidate":
        for field, expected in {"disposition": "provisional", "endorsement": "none", "frozen": True}.items():
            _equal(record[field], expected, location + "." + field)
        _choice(record["review_status"], ("awaiting_challenge", "pending_review"), location + ".review_status")
        _choice(record["support_use"], ("incomplete", "requires_applicability_review"), location + ".support_use")
    elif kind == "justification":
        _choice(record["method"], ("analytical", "finite_matrix", "translated_trial_state"), location + ".method")
        _choice(record["scope"], ("formal_harmonic_moments", "finite_projection", "negative_full_line"), location + ".scope")
    elif kind == "evidence":
        _choice(record["purpose"], ("harmonic_limit", "basis_construction", "negative_existence"), location + ".purpose")
        _choice(record["scope"], ("harmonic_baseline", "finite_projection", "negative_full_line"), location + ".scope")
        _choice(record["expected_outcome"], ("pass", "fail"), location + ".expected_outcome")
    elif kind == "task":
        _equal(record["expected_outcome"], "completed", location + ".expected_outcome")
        _equal(record["scope"], "finite_projection", location + ".scope")
    elif kind == "review":
        for field, expected in {
            "expected_outcome": "refuted_within_scope", "refuted_scope": "negative_full_line",
            "preserved_scopes": ["formal_harmonic_moments", "finite_projection"],
            "independence": "none_no_blind_or_independent_review", "all_authored_together": True,
        }.items():
            _equal(record[field], expected, location + "." + field)
    elif kind == "issue":
        _equal(record["disposition"], "negative_interpretation_refuted", location + ".disposition")
    elif kind == "snapshot":
        _choice(record["stage"], _STAGES, location + ".stage")
        _equal(record["novelty"], "unassessed", location + ".novelty")
        _equal(record["endorsement"], "none", location + ".endorsement")
    elif kind == "proposed_question":
        _equal(record["status"], "proposed_requires_new_specification", location + ".status")
    elif kind == "partial_report":
        _equal(record["stop_reason"], "paper walkthrough stops pending review", location + ".stop_reason")
        _equal(record["pending_review"], True, location + ".pending_review")
        resources = record["resources"]
        _fields(resources, {"execution", "usage", "cost", "liability", "statement"}, location + ".resources")
        for field in ("execution", "usage", "cost", "liability"):
            _fields(resources[field], {"status", "value"}, location + ".resources." + field)
            _equal(resources[field]["status"], "not_applicable" if field == "execution" else "not_measured",
                   location + ".resources." + field + ".status")
            _equal(resources[field]["value"], None, location + ".resources." + field + ".value")
        _equal(resources["statement"], "No real account/resource conclusion follows from this fixture.", location + ".resources.statement")


def _validate_scenario(records, walkthrough):
    """Check this paper narrative's exact history and scoped expected state transitions."""
    def one(kind, field=None, value=None):
        """Select a required unique narrative role, including its explicit revision."""
        found = [r for r in records if r["kind"] == kind and (field is None or r[field] == value)]
        _require(len(found) == 1, f"scenario.{kind}.{value}", "expected exactly one narrative role")
        return found[0]

    seed = one("seed")
    original_context = one("context", "scope", "both_signs")
    positive_context = one("context", "scope", "positive")
    original = one("candidate", "review_status", "awaiting_challenge")
    positive = one("candidate", "review_status", "pending_review")
    harmonic = one("evidence", "purpose", "harmonic_limit")
    basis = one("evidence", "purpose", "basis_construction")
    negative = one("evidence", "purpose", "negative_existence")
    algebra = one("justification", "method", "analytical")
    matrix = one("justification", "method", "finite_matrix")
    argument = one("justification", "method", "translated_trial_state")
    task, review, issue = one("task"), one("review"), one("issue")
    question, report = one("proposed_question"), one("partial_report")
    snapshots = [one("snapshot", "stage", stage) for stage in _STAGES]
    _require(original["id"] != positive["id"], "scenario.positive.id", "must be a distinct candidate identity")
    _require(original_context["id"] != positive_context["id"], "scenario.positive.context", "must be a distinct context identity")
    obligations = []
    for context in (original_context, positive_context):
        group = []
        for category in ("existence_domain", "approximation", "convergence"):
            found = [r for r in records if r["kind"] == "obligation" and r["context"] == _ref(context) and r["category"] == category]
            _require(len(found) == 1, "scenario.obligations." + category, "one unresolved obligation per context required")
            group.extend(found)
        obligations.append(group)
    old_obligations, new_obligations = obligations
    _equal(seed["context"], _ref(original_context), "seed.context")
    for record in (original, harmonic, basis, negative, algebra, matrix, argument, task, review, issue):
        _equal(record["context"], _ref(original_context), record["id"] + ".context")
    _equal(positive["context"], _ref(positive_context), positive["id"] + ".context")
    for candidate, parent, use, group in (
        (original, None, "incomplete", old_obligations),
        (positive, _ref(original), "requires_applicability_review", new_obligations),
    ):
        _equal(candidate["derived_from"], parent, candidate["id"] + ".derived_from")
        _equal(candidate["support_use"], use, candidate["id"] + ".support_use")
        _same_refs(candidate["justifications"], [algebra, matrix], candidate["id"] + ".justifications")
        _same_refs(candidate["obligations"], group, candidate["id"] + ".obligations")
    for evidence, scope, outcome in ((harmonic, "harmonic_baseline", "pass"), (basis, "finite_projection", "pass"), (negative, "negative_full_line", "fail")):
        for field, expected in {"scope": scope, "expected_outcome": outcome,
                                "target": _ref(original) if evidence is negative else None,
                                "argument": _ref(argument) if evidence is negative else None}.items():
            _equal(evidence[field], expected, evidence["id"] + "." + field)
    for justification, scope, evidence in ((algebra, "formal_harmonic_moments", harmonic), (matrix, "finite_projection", basis), (argument, "negative_full_line", negative)):
        _equal(justification["scope"], scope, justification["id"] + ".scope")
        _same_refs(justification["evidence"], [evidence], justification["id"] + ".evidence")
    _equal(task["justification"], _ref(matrix), task["id"] + ".justification")
    _same_refs(task["evidence"], [basis], task["id"] + ".evidence")
    for record in (review, issue):
        _equal(record["target"], _ref(original), record["id"] + ".target")
        _equal(record["argument"], _ref(argument), record["id"] + ".argument")
        _same_refs(record["evidence"], [harmonic, basis, negative], record["id"] + ".evidence")
    _equal(issue["review"], _ref(review), issue["id"] + ".review")
    # A completed finite task never becomes support for full-line existence.
    state_tuples = (
        ("exploring", "provisional", "unresolved"),
        ("frozen_candidate", "provisional", "requires_reassessment"),
        ("reconciled", "refuted_within_negative_scope", "negative_full_line_inapplicable"),
        ("partial_stop", "provisional_pending_review", "requires_applicability_review"),
    )
    for i, snapshot in enumerate(snapshots):
        location = snapshot["id"]
        work, disposition, applicability = state_tuples[i]
        expected = {
            "task": _ref(task), "candidate": None if i == 0 else _ref(positive if i == 3 else original),
            "context": _ref(positive_context if i == 3 else original_context),
            "review": _ref(review) if i == 2 else None,
            "issue": _ref(issue) if i >= 2 else None,
            "historical_candidate": None if i == 0 else _ref(original),
            "operational_status": "completed", "work_stage": work,
            "scientific_disposition": disposition, "applicability": applicability,
            "support": [
                {"type": "analytical", "scope": "formal_harmonic_moments", "applicability": "limited_scope_only"},
                {"type": "numerical", "scope": "finite_projection", "applicability": "limited_scope_only"},
            ],
        }
        for field, value in expected.items():
            _equal(snapshot[field], value, location + "." + field)
        _same_refs(snapshot["evidence"], [harmonic, basis] + ([negative] if i >= 2 else []), location + ".evidence")
        for field in ("retained_obligations", "outstanding_obligations"):
            _same_refs(snapshot[field], old_obligations + (new_obligations if i == 3 else []), location + "." + field)
    _equal(question["derived_from"], _ref(original), question["id"] + ".derived_from")
    for field, record in {"snapshot": snapshots[3], "historical_candidate": original, "review": review,
                          "issue": issue, "task": task, "pending_candidate": positive, "followup": question}.items():
        _equal(report[field], _ref(record), report["id"] + "." + field)
    for field, group in {"contexts": [original_context, positive_context], "evidence": [harmonic, basis, negative],
                         "justifications": [algebra, matrix, argument], "obligations": old_obligations + new_obligations}.items():
        _same_refs(report[field], group, report["id"] + "." + field)
    order = [seed, original_context, *old_obligations, harmonic, basis, algebra, matrix, task,
             snapshots[0], original, snapshots[1], argument, negative, review, issue, snapshots[2],
             positive_context, *new_obligations, positive, question, snapshots[3], report]
    _same_refs(walkthrough, order, "walkthrough")
    _require(len(records) == len(order), "records", "records must have a declared narrative role")


def validate_oscillator_fixture(data) -> None:
    """Validate a JSON-shaped example without mutation; raise a located contract error.

    Checks provenance, typed exact links and expected scenario relationships, not
    scientific correctness, authentic execution, expert judgment or independence.
    """
    _fields(data, {"schema_version", "fixture_version", "metadata", "records", "walkthrough"}, "fixture")
    _equal(data["schema_version"], 1, "schema_version")
    _equal(data["fixture_version"], "1.0.0", "fixture_version")
    metadata = {
        "source": "project_description.md", "section": "13.1",
        "specification_sha256": "13d2ed9198916b7af3a3f9c3522745b0b6882b5492c9e27ccdc0c46114137ab7",
        "origin": "synthetic_local", "visibility": "development", **_PROVENANCE,
    }
    _fields(data["metadata"], metadata, "metadata")
    for field, value in metadata.items():
        _equal(data["metadata"][field], value, "metadata." + field)
    _require(type(data["records"]) is list and bool(data["records"]), "records", "expected nonempty list")
    index, identities = {}, {}
    for i, record in enumerate(data["records"]):
        location = f"records[{i}]"
        _require(type(record) is dict, location, "expected object")
        _choice(record.get("kind"), _FIELDS, location + ".kind")
        _fields(record, _COMMON | set(_FIELDS[record["kind"]].split()), location)
        _require(type(record["id"]) is str and bool(record["id"].strip()), location + ".id", "expected nonempty string")
        _require(type(record["revision"]) is int and record["revision"] > 0, location + ".revision", "expected positive integer")
        key = (record["id"], record["revision"])
        _require(key not in index, location, "duplicate identity/revision")
        _require(identities.get(record["id"], record["kind"]) == record["kind"], location, "inconsistent kind across identity")
        index[key], identities[record["id"]] = record, record["kind"]
    for i, record in enumerate(data["records"]):
        _validate_record(record, index, f"records[{i}]({record['id']}@{record['revision']})")
    _references(data["walkthrough"], index, tuple(_FIELDS), "walkthrough")
    _validate_scenario(data["records"], data["walkthrough"])


def _unique_object(pairs):
    """Reject ambiguous duplicate JSON keys, retaining the offending key in errors."""
    result = {}
    for key, value in pairs:
        _require(key not in result, f"JSON object key {key!r}", "duplicate key")
        result[key] = value
    return result


def _reject_constant(value):
    """Reject Python JSON extensions for nonfinite numbers before contract validation."""
    raise FixtureValidationError(f"JSON value {value}: nonfinite numbers are forbidden")


def load_oscillator_fixture(path=None) -> dict:
    """Read fresh UTF-8 JSON from path (caller-relative) or source-local evaluations.

    Import performs no reads. Missing/unreadable inputs retain ordinary OSError
    failures; encoding, JSON and contract failures include the source path in
    FixtureValidationError. Loading has no cache, acquisition or write fallback.
    """
    source = Path(path) if path is not None else Path(__file__).resolve().parents[2] / "evaluations" / "harmonic_quartic_v1.json"
    try:
        data = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
        validate_oscillator_fixture(data)
    except (ValueError, UnicodeError) as error:
        raise FixtureValidationError(f"{source}: {error}") from error
    return data
