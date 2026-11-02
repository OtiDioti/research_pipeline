"""Explicit v2 readable projections of exact committed report history, without store access."""

import hashlib
import posixpath
import re

from research_pipeline.domain import ArtifactReference, DomainValidationError
from research_pipeline.snapshot import DetachedSnapshot, SnapshotLimits, SnapshotLimitError, _canonical
from research_pipeline import reports
from research_pipeline.view_plan import (
    ReadablePlan, ViewPlanError, _plan_inventory, _snapshot_from_manifest,
    _link, _literal, _markdown_navigation, _HEADINGS,
)
from research_pipeline.work_product import _path


def report_directory(item):
    """Use the actual portable run identity; unsafe record identifiers fail rather than being renamed."""
    request = item["observation"]["request"]
    run = request["run"]["record_id"]
    if len(_path(run, "report run")) != 1 or len(run.encode("ascii")) > 128:
        raise ViewPlanError("report run must be one portable component")
    return "reports/runs/" + run + "/" + str(request["report_revision"])


def report_mappings(item):
    """Bind independent publication copies to their exact manifest occupant and declared provenance."""
    result, observation = item["result"], item["observation"]
    base = report_directory(item)
    for name, artifact in sorted(result["artifacts"].items()):
        yield dict(logical_key=dict(record_id=result["report_manifest"]["record_id"],
            revision=result["report_manifest"]["revision"], role="committed_report_file",
            identifier=name, original_path=name), relative_path=base + "/" + name,
            digest=artifact["digest"], size=artifact["size"], availability="expected_unverified",
            hash_kind="expected", provenance=observation["request"]["provenance"],
            details=dict(original_path=name, entry_file=name == "report.md", product_kind="end_of_run_report",
                         authors=observation["request"]["authors"], media_declaration=None,
                         original_mode=None, restrictions=None))


def _within(observation, limits):
    """Check every retained snapshot allowance, including mixed-version nested saved baselines."""
    current = observation
    while True:
        embedded = current["scientific"]["limits"]
        if any(value > limits.to_dict()[key] for key, value in embedded.items()):
            raise SnapshotLimitError("retained report snapshot allowance exceeds caller limits")
        if len(_canonical(current)) > limits.max_metadata_bytes:
            raise SnapshotLimitError("retained report exceeds metadata allowance")
        baseline = current["baseline"]
        if "observation" not in baseline:
            break
        current = baseline["observation"]


def validate_reports(snapshot, entries, limits):
    """Validate complete ordered history and exact source/result/receipt/scientific bindings.

    Detached consistency is not authentication. Canonical preparation separately
    verifies the original committed operations and objects in a read transaction.
    The selected report's own submission stays outside its scientific watermark.
    """
    document = snapshot.to_dict()
    if type(entries) is not list or not entries or len(entries) > limits.max_records:
        raise ViewPlanError("bounded nonempty complete report history required")
    records = {reports.pin(r): r for r in document["records"]}
    artifacts = {a["digest"]: a["size"] for a in document["artifacts"]}
    identities, metadata, references, copy_bytes = set(), 0, 0, 0
    stable = None
    previous_event = 0
    for revision, item in enumerate(entries, 1):
        reports._fields_exact(item, "result observation", "readable report")
        metadata += len(_canonical(item))
        if metadata > limits.max_metadata_bytes:
            raise SnapshotLimitError("retained report history exceeds metadata allowance")
        observation = reports.ReportObservation(item["observation"])
        value = observation.to_dict()
        result = reports.ReportCommitResult(item["result"])
        outcome, request = result.to_dict(), value["request"]
        _within(value, limits)
        report_directory(item)
        scope = tuple(request[k]["record_id"] for k in ("project", "run"))
        if stable is None:
            stable = scope
        if (scope != stable or request["report_revision"] != revision
                or request["operation_id"] in identities or outcome["operation_id"] != request["operation_id"]
                or any(outcome[k] != value[k] for k in ("snapshot_id", "observed_at"))):
            raise ViewPlanError("report history must be a complete same-run chain of distinct operations")
        identities.add(request["operation_id"])
        objects = reports._artifact_map(outcome["artifacts"])
        outputs = {"source.json": reports.dumps_observation(observation).encode("ascii"),
                   **reports.render_report(observation)}
        for name, data in outputs.items():
            if objects[name] != ArtifactReference(hashlib.sha256(data).hexdigest(), len(data)):
                raise ViewPlanError("report output differs from original source binding")
            copy_bytes += len(data)
            if len(data) > limits.max_file_bytes or copy_bytes > limits.max_total_bytes:
                raise SnapshotLimitError("report copies exceed caller byte allowances")
        submission = reports._submission(value, objects)
        receipt = result.receipt
        fingerprint = hashlib.sha256(_canonical(dict(fingerprint_version=1, submission=submission.to_dict())).encode("ascii")).hexdigest()
        if (receipt.fingerprint != fingerprint or receipt.submission_id != submission.submission_id
                or _canonical(receipt.provenance.to_dict()) != _canonical(submission.provenance.to_dict())
                or receipt.revisions != tuple((r.record_id, r.revision) for r in submission.records)
                or receipt.event_id != value["scientific"]["watermark"]["event_id"] + 1
                or receipt.event_id <= previous_event):
            raise ViewPlanError("report receipt differs from derived submission or scientific watermark")
        previous_event = receipt.event_id
        references += len(value["source_bindings"]) + sum(len(r.record_references) + len(r.artifact_references) for r in submission.records)
        if references > limits.max_references or 3 * revision > limits.max_artifacts:
            raise SnapshotLimitError("report history references or copies exceed allowances")
        for row in value["scientific"]["records"]:
            if _canonical(records.get(reports.pin(row))) != _canonical(row):
                raise ViewPlanError("historical exact record missing or inconsistent in selected inventory")
        for artifact in value["scientific"]["artifacts"]:
            if artifacts.get(artifact["digest"]) != artifact["size"]:
                raise ViewPlanError("historical artifact missing or inconsistent in selected inventory")
        if revision < len(entries):
            for envelope in submission.records:
                row = records.get((envelope.record_id, envelope.revision))
                if (row is None or row["envelope_json"] != _canonical(envelope.to_dict())
                        or row["commit"] != dict(submission_id=receipt.submission_id,
                            fingerprint=receipt.fingerprint, committed_at=receipt.committed_at)):
                    raise ViewPlanError("historical report submission is absent from selected source closure")
    if _canonical(entries[-1]["observation"]["scientific"]) != _canonical(document):
        raise ViewPlanError("navigation inventory must be the selected report's original scientific snapshot")
    return entries


def plan_report_snapshot(snapshot, entries, *, limits):
    """Project validated retained reports with original snapshot output limits and independent caller bounds."""
    if type(snapshot) is not DetachedSnapshot or type(limits) is not SnapshotLimits:
        raise DomainValidationError("expected DetachedSnapshot and SnapshotLimits")
    limits = SnapshotLimits(**limits.to_dict())
    validate_reports(snapshot, entries, limits)
    return ReadablePlan(*_plan_inventory(snapshot, entries))


def report_home(entries):
    """Prominently identify the selected dated report and saved requirements without proposing action."""
    selected = entries[-1]
    value = selected["observation"]
    declaration = value["request"]["declarations"]
    yield "# Selected captured run report\n\n"
    yield "This is a saved dated observation. Reading or publishing never authorizes continuation.\n\n"
    base = report_directory(selected)
    yield _link("README.md", base + "/report.md", "Selected report") + " · "
    yield _link("README.md", base + "/README.md", "Exact evidence navigation") + "\n\n"
    yield from _literal(dict(operation_id=selected["result"]["operation_id"], snapshot_id=value["snapshot_id"],
        observed_at=value["observed_at"], qualified_outcome=declaration["outcome"],
        recorded_stopping_declaration=declaration["stop_reason"], saved_continuation_requirements=declaration["continuation"]))
    yield "Prior captured revisions:\n\n"
    if len(entries) == 1:
        yield "None in this saved chain.\n\n"
    for item in entries[:-1]:
        base = report_directory(item)
        yield _link("README.md", base + "/report.md", "Report " + str(item["observation"]["request"]["report_revision"])) + " · "
        yield _link("README.md", base + "/README.md", "Evidence navigation") + "\n\n"
        yield from _literal(item["observation"]["observed_at"])


def report_navigation(item, entries, paths, mappings):
    """Link only exact records and artifacts retained by this report's own observation."""
    observation = item["observation"]
    base = report_directory(item)
    page = base + "/README.md"
    own = {reports.pin(r): r for r in observation["scientific"]["records"]}
    envelopes = reports._envelopes(observation["scientific"])
    yield "# Saved report evidence navigation\n\n## Purpose and scope\n\n"
    yield "Exact saved evidence for this dated observation; unavailable or unselected material is unknown.\n\n"
    yield "## Contents\n\n"
    for name, label in (("report.md", "Report"), ("source.json", "Saved source"), ("continuation.json", "Saved continuation")):
        yield _link(page, base + "/" + name, label) + "\n\n"
    for label, kinds in (("Claims", ("claim",)), ("Evidence", ("evidence",)), ("Reviews", ("review",)),
                         ("Issues and objections", ("issue",)), ("Derivations and calculations", ("justification", "work_product_manifest")),
                         ("Saved work and checkpoints", ("work_product_manifest",))):
        yield "### " + label + "\n\n"
        found = False
        for key, envelope in envelopes.items():
            if envelope.kind not in kinds:
                continue
            if label == "Derivations and calculations" and envelope.kind == "work_product_manifest" and envelope.content.get("product_kind") not in ("derivation", "calculation"):
                continue
            found = True
            yield _link(page, paths[key], key[0] + "@" + str(key[1])) + " · "
            yield _link(page, posixpath.dirname(paths[key]) + "/envelope.json", "Exact envelope") + "\n\n"
            for mapping in mappings.get(key, ()):
                yield _link(page, mapping["relative_path"], "Exact artifact " + mapping["logical_key"]["identifier"]) + "\n\n"
        if not found:
            yield "Unavailable or not selected in this saved observation.\n\n"
    yield "### Continuation dependencies\n\n"
    continuation = observation["request"]["declarations"]["continuation"]
    refs = list(reports._walk_references(continuation))
    if not refs:
        yield "No saved exact continuation targets; requirements remain unavailable.\n\n"
    for ref in refs:
        key = reports.pin(ref)
        if key not in own:
            raise ViewPlanError("saved continuation target absent")
        yield _link(page, paths[key], ref["relationship"] + " " + key[0] + "@" + str(key[1])) + "\n\n"
    yield "## Current work\n\nOnly saved declarations are displayed; no next action is inferred.\n\n"
    yield "## Provenance\n\n"
    yield from _literal(dict(operation_id=item["result"]["operation_id"], snapshot_id=observation["snapshot_id"], observed_at=observation["observed_at"]))
    yield "## Use\n\n" + _link(page, "README.md", "Home") + "\n\n"
    for prior in entries:
        if prior["observation"]["request"]["report_revision"] < observation["request"]["report_revision"]:
            yield _link(page, report_directory(prior) + "/README.md", "Historical revision " + str(prior["observation"]["request"]["report_revision"])) + "\n\n"
    yield "## Dependencies and limitations\n\nOutgoing saved closure only; links do not establish support or authority. Authored artifact links remain uncertified.\n\n"
    yield "## Editing route\n\nPreserved edits are unsubmitted proposed work; they never replace committed report bytes.\n"


def verify_report_plan(plan, manifest):
    """Recompute all v2 bytes and verify generated navigation, including trusted saved report renderers."""
    snapshot = DetachedSnapshot(_snapshot_from_manifest(manifest))
    limits = SnapshotLimits(**manifest["limits"])
    entries = validate_reports(snapshot, manifest["reports"], limits)
    expected = _plan_inventory(snapshot, entries)
    actual = (plan.snapshot_id, plan.plan_id, plan.generated_files, plan.artifact_copies, plan.directories, plan.manifest_bytes)
    if expected != actual:
        raise ViewPlanError("v2 plan differs from complete canonical projection")
    files = {f.relative_path for f in (*plan.generated_files, *plan.artifact_copies)}
    markdown = {f.relative_path: _markdown_navigation(f.data) for f in plan.generated_files if f.relative_path.endswith(".md")}
    for item in entries:
        data = reports.render_report(reports.ReportObservation(item["observation"]))["report.md"].decode("utf-8")
        # Only exact renderer bytes are trusted, never arbitrary copied Markdown.
        links = [link for line in data.splitlines() if not line.startswith("    ")
                 for link in re.findall(r"\[[^\[\]\n]*\]\(([^)]+)\)", line)]
        markdown[report_directory(item) + "/report.md"] = (set(), links)
    for page, (headings, links) in markdown.items():
        if page.endswith("/README.md") or page == "README.md":
            if not {h.lower().replace(" ", "-") for h in _HEADINGS} <= headings:
                raise ViewPlanError("README missing fixed folder fields")
        for link in links:
            if link.startswith("/") or any(c in link for c in (":", "\\", "%", "?")) or link.count("#") > 1:
                raise ViewPlanError("unsafe report navigation")
            path, separator, fragment = link.partition("#")
            target = posixpath.normpath(posixpath.join(posixpath.dirname(page), path)) if path else page
            if target not in files or (separator and (target not in markdown or fragment not in markdown[target][0])):
                raise ViewPlanError("report navigation target missing")
