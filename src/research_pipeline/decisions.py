"""Version-bound terminal review receipts. Scientific adequacy is agent judgment."""
import json

from . import workspace, verification

PROPOSAL_FIELDS = ("Results", "Assumptions", "Evidence and reproduction", "Reasons",
                   "Recovery attempts", "Unfinished work", "Continuation guidance",
                   "Responses to objections", "Decision record")
REVIEW_FIELDS = ("Independent approach", "Observations and counterchecks", "Evidence",
                 "Objections and limitations", "Review record")
FINAL_FIELDS = ("Reasons", "Response to challenge", "Unfinished work",
                "Continuation guidance", "Decision record")
DISPOSITIONS = {"answered", "negative", "inconclusive", "unanswerable", "unresolved"}
HISTORY_PAGE_SIZE = 4


def summary(proposal):
    """References and counts only; scientific arguments are read in text pages."""
    result = {key: proposal[key] for key in ("id", "intent", "version", "phase", "previous")}
    result["invalidated"] = bool(proposal.get("invalidated"))
    result["question_count"] = len(proposal["coverage"])
    result["packet"] = {key: proposal["packet"][key] for key in ("packet", "manifest", "version")}
    result["readable_parts"] = ["proposal"]
    if proposal.get("review"):
        review = proposal["review"]
        result["review"] = {
            "outcome": review["outcome"], "exhaustive": review["exhaustive"],
            "objection_count": len(review["objections"]),
            "open_substantive_count": sum(o["substantive"] and o["disposition"] == "open"
                                          for o in review["objections"]),
            "path": proposal["review_path"], "sha256": proposal["review_sha256"],
            "context_id": proposal["review_context_id"]}
        result["review"]["packet"] = {key: proposal["review_packet"][key]
                                     for key in ("packet", "manifest", "version")}
        result["readable_parts"].append("review")
    if proposal.get("final_request"):
        result["readable_parts"].append("final")
    return result


def record(text, fields, heading):
    parts = verification.sections(text, fields)
    raw = parts[heading]
    if raw.startswith("```json\n") and raw.endswith("\n```"):
        raw = raw[8:-4]
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise workspace.InputError(f"## {heading} must contain one JSON object") from exc
    if not isinstance(value, dict):
        raise workspace.InputError(f"## {heading} must contain one JSON object")
    return value


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise workspace.InputError(f"Missing substantive {label}")
    return value


def proposal(text, intent):
    value = record(text, PROPOSAL_FIELDS, "Decision record")
    coverage = value.get("coverage")
    if not isinstance(coverage, list) or not coverage:
        raise workspace.InputError("Enumerate coverage of every current question")
    ids = set()
    for item in coverage:
        if not isinstance(item, dict):
            raise workspace.InputError("Invalid question coverage")
        identifier = nonempty(item.get("id"), "question id")
        if identifier in ids:
            raise workspace.InputError("Duplicate question id")
        ids.add(identifier)
        nonempty(item.get("question"), "question")
        nonempty(item.get("explanation"), "coverage explanation")
        if item.get("disposition") not in DISPOSITIONS:
            raise workspace.InputError("Unknown question disposition")
        if intent == "COMPLETE" and item["disposition"] == "unresolved":
            raise workspace.InputError("Unresolved questions prevent COMPLETE")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not all(isinstance(p, str) and p for p in evidence):
            raise workspace.InputError("Coverage evidence must list presented artifact sources")
        if item["disposition"] != "unresolved" and not evidence:
            raise workspace.InputError("Supported coverage requires evidence")
    return value


def review(text, proposal, previous=()):
    fields = REVIEW_FIELDS + (("Stopping rationale", "Further work") if proposal["intent"] == "STOP" else ())
    value = record(text, fields, "Review record")
    if value.get("version") != proposal["version"]:
        raise workspace.InputError("Review refers to a stale proposal version")
    if value.get("outcome") not in {"agree_complete", "needs_revision", "stop_challenged"}:
        raise workspace.InputError("Unknown opposition outcome")
    if type(value.get("exhaustive")) is not bool:
        raise workspace.InputError("Opponent must judge exhaustiveness of question coverage")
    coverage = value.get("coverage")
    expected = {q["id"] for q in proposal["coverage"]}
    if (not isinstance(coverage, list) or len(coverage) != len(expected)
            or any(not isinstance(q, dict) for q in coverage)
            or {q.get("id") for q in coverage} != expected):
        raise workspace.InputError("Opponent must assess each presented question")
    for item in coverage:
        if type(item.get("adequate")) is not bool:
            raise workspace.InputError("Opponent must judge scientific adequacy")
        nonempty(item.get("reason"), "adequacy reason")
    objections = value.get("objections")
    if not isinstance(objections, list):
        raise workspace.InputError("Opponent must retain objection dispositions")
    identifiers = set()
    for item in objections:
        if not isinstance(item, dict):
            raise workspace.InputError("Invalid objection")
        identifier = nonempty(item.get("id"), "stable objection id")
        if identifier in identifiers:
            raise workspace.InputError("Duplicate objection id")
        identifiers.add(identifier)
        if type(item.get("substantive")) is not bool or item.get("disposition") not in {
                "open", "resolved", "withdrawn", "inapplicable"}:
            raise workspace.InputError("Invalid objection classification/disposition")
        nonempty(item.get("reason"), "objection reasoning")
    if not set(previous).issubset(identifiers):
        raise workspace.InputError("Carry forward all prior objection IDs with reasons")
    if value["outcome"] == "agree_complete":
        if proposal["intent"] != "COMPLETE" or not eligible(value):
            raise workspace.InputError("Agreement requires exhaustive adequate coverage and no open substantive objection")
    if proposal["intent"] == "STOP" and value["outcome"] != "stop_challenged":
        raise workspace.InputError("STOP requires a challenge to findings and stopping rationale")
    return value


def eligible(review):
    return (review.get("exhaustive") is True
            and all(q["adequate"] for q in review["coverage"])
            and not any(o["substantive"] and o["disposition"] == "open" for o in review["objections"]))


def final(text, proposal, tasks, opponent):
    value = record(text, FINAL_FIELDS, "Decision record")
    if value.get("version") != proposal["version"]:
        raise workspace.InputError("Final decision refers to a stale proposal")
    dispositions = value.get("delegated_work")
    if not isinstance(dispositions, dict):
        raise workspace.InputError("Reconcile delegated work explicitly")
    for identifier in tasks:
        if identifier in ("primary", opponent):
            continue
        item = dispositions.get(identifier, {})
        if item.get("disposition") not in {"integrated", "superseded", "no_longer_needed"}:
            raise workspace.InputError("Unreconciled delegated work: " + identifier)
        if item["disposition"] == "integrated" and not tasks[identifier].get("released"):
            raise workspace.InputError("Finish and inspect delegated work before declaring it integrated: " + identifier)
        nonempty(item.get("reason"), "delegated work disposition reason")
    return value
