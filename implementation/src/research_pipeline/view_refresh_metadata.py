"""Strict refresh representations and deterministic inert continuation reports."""

from dataclasses import dataclass, fields
from urllib.parse import quote

from research_pipeline.domain import DomainValidationError, _integer
from research_pipeline.snapshot import SnapshotLimits, SnapshotLimitError, _bounded_json, _canonical
from research_pipeline.vault import ViewIntegrityError, ViewDifference
from research_pipeline.view_capture import CaptureLimits, _limits as _capture_limits, _digest, _identified, _Metadata
from research_pipeline.view_plan import _literal


LIMITATIONS = (
    "Preservation is unsubmitted proposed work; canonical records and historical paths are unchanged.",
    "No automatic import, scientific endorsement, execution, configuration or policy activation.",
    "Successor generated links/headings are mechanically verified; authored and prior edited links are neither certified nor repaired.",
    "Local checks detect observed mutations, not coherent hostile same-owner or privileged rewrites; no editor lock is supplied.",
    "Present evidence cannot establish historical fsync acknowledgment, admission or authentication.",
)
ATTEMPT_LIMITATIONS = (
    "No automatic replay, cleanup, repair or rollback.",
    "Observations are not acceptance receipts or proof of historical fsync acknowledgment.",
)


@dataclass(frozen=True)
class RefreshLimits:
    """Explicit independent capture/successor and complete package/resource allowances."""

    capture_limits: CaptureLimits
    successor_limits: SnapshotLimits
    max_entries: int
    max_files: int
    max_directories: int
    max_depth: int
    max_file_bytes: int
    max_total_bytes: int
    max_metadata_bytes: int
    max_diagnostics: int
    max_open_descriptors: int

    def __post_init__(self):
        """Detach nested allowances and reject coercions, booleans and bypass-mutated values."""
        object.__setattr__(self, "capture_limits", _capture_limits(self.capture_limits))
        if type(self.successor_limits) is not SnapshotLimits:
            raise DomainValidationError("successor_limits: expected SnapshotLimits")
        object.__setattr__(self, "successor_limits", SnapshotLimits(**self.successor_limits.to_dict()))
        for field in fields(self):
            if field.name not in ("capture_limits", "successor_limits"):
                _integer(getattr(self, field.name), field.name,
                         0 if field.name in ("max_file_bytes", "max_total_bytes") else 1)


def _limits_value(value):
    """Revalidate exact public limits and detach all nested caller state."""
    if type(value) is not RefreshLimits:
        raise DomainValidationError("limits: expected RefreshLimits")
    return RefreshLimits(**{f.name: getattr(value, f.name) for f in fields(value)})


@dataclass(frozen=True)
class RefreshedReadableView:
    """Completed local publication observation; paths identify concrete pinned generations."""

    refresh_id: str
    prior_view: str
    prior_snapshot_id: str
    prior_plan_id: str
    capture_id: str
    preservation_plan_id: str
    successor_snapshot_id: str
    successor_plan_id: str
    destination: str
    successor_path: str
    preservation_path: str
    attempt_path: str
    same_plan: bool
    verification: str = "verified_at_refresh"


@dataclass(frozen=True)
class RefreshInspection:
    """Current read-only evidence classification, never a historical acknowledgment receipt."""

    status: str
    refresh_id: str | None
    verified_package_path: str | None
    successor_path: str | None
    preservation_path: str | None
    readiness_observation: str
    publication_observation: str
    historical_acknowledgment: str
    differences: tuple[ViewDifference, ...]


def _relationships(prior, successor, maximum):
    """Map exact revisions/roots and reject dropping or changing previously published report bindings.

    Scientific selections may change, but explicit immutable report history must
    remain an identical prefix of the successor. Legacy v1 mappings stay unchanged.
    """
    old, new = prior.to_dict(), successor.to_dict()
    if (old["selection"]["project"]["record_id"] != new["selection"]["project"]["record_id"]
            or old["resolutions"][0]["record_id"] != new["resolutions"][0]["record_id"]):
        raise ViewIntegrityError("refresh plans identify different projects")
    # Publication history is append-only even though scientific selections may change.
    old_reports, new_reports = old.get("reports", []), new.get("reports", [])
    if _canonical(new_reports[:len(old_reports)]) != _canonical(old_reports):
        raise ViewIntegrityError("refresh successor drops or changes published report bindings")
    inventories = [{(r["record_id"], r["revision"]): r for r in d["records"]} for d in (old, new)]
    keys = sorted(set(inventories[0]) | set(inventories[1]))
    if len(keys) > maximum:
        raise SnapshotLimitError("max_diagnostics exceeded by refresh record mappings")
    rows = []
    for key in keys:
        row = dict(record_id=key[0], revision=key[1])
        for label, document, inventory in zip(("prior", "successor"), (old, new), inventories):
            row[label + "_page_path"] = inventory[key]["page_path"] if key in inventory else None
            row[label + "_root_ordinals"] = [i for i, r in enumerate(document["resolutions"])
                if (r["record_id"], r["revision"]) == key]
        rows.append(row)
    return dict(prior_requested=old["selection"], prior_resolutions=old["resolutions"],
                successor_requested=new["selection"], successor_resolutions=new["resolutions"]), rows


def _report(capture, preservation, prior, successor, selection, records, maximum):
    """Render bounded fixed prose, inert canonical mappings and encoded preserved-path links."""
    def parts():
        """Yield escaped data incrementally so supplied names cannot create active Markdown."""
        yield ("# Preserved readable refresh\n\nOpen and pin **destination/generation** as the reading vault. "
               "Preservation is **unsubmitted proposed work**. The entire prior tree remains at its original "
               "location with its human edits and renames intact.\n\n"
               "[Open successor](generation/README.md) · [Refresh association](refresh.json) · "
               "[Capture metadata](capture.json) · [Preservation plan](preservation-plan.json)\n\n")
        for line in LIMITATIONS:
            yield line + "\n\n"
        yield ("The retained preservation plan is still planned_only; refresh.json separately binds its "
               "completed copies to this successor. Legacy version-1 generated availability wording "
               "describes the original projection; the separate refresh API now supplies this operation.\n\n")
        for label, value in (("Prior location", capture["prior_view"]), ("Prior snapshot", prior.snapshot_id),
                             ("Prior plan", prior.plan_id), ("Capture", capture["capture_id"]),
                             ("Preservation plan", preservation["preservation_plan_id"]),
                             ("Successor snapshot", successor.snapshot_id), ("Successor plan", successor.plan_id),
                             ("Requested selections and exact resolutions", selection)):
            yield label + ":\n\n"
            yield from _literal(value)
        yield "## Exact record mappings\n\nNull successor paths identify omitted revisions; historical dependencies remain separate rows.\n\n"
        for row in records:
            yield from _literal(row)
        yield "## Prior target diagnostics\n\nMissing paths, moved directories and duplicate-content groups are observations, not repairs.\n\n"
        for row in preservation["target_diagnostics"]:
            yield from _literal(row)
            if row["preservation_path"] is not None:
                yield "[Preserved target](" + quote("preservation/" + row["preservation_path"], safe="/") + ")\n\n"
        for row in preservation["rename_groups"]:
            yield from _literal(row)
        yield ("Rename-plus-edit and ambiguous identities require manual mapping. Inventory inspection "
               "does not prove which arbitrary authored Markdown/wikilinks are broken. Frozen authored "
               "bundles retain original bytes and scientific paths.\n\n## Explicit work-product continuation\n\n"
               "Use the exact historical record/revision and logical bundle path from the original mappings below. "
               "Call checkout_work_product with RecordReference(record_id, revision, 'checkout_base', "
               "'work_product_manifest') into a new independent destination. Copy only explicitly chosen preserved "
               "bytes into the intended logical checkout path. Call prepare_work_product_import with "
               "expected_head=that revision, complete metadata, explicit selected_paths, attribution, limits and "
               "a fresh submission ID. Review its summary; durably save the proposal with the existing codecs; "
               "separately call submit_typed. Preview may publish immutable objects but changes no canonical "
               "metadata; refresh performs neither action. A stale base must conflict rather than rebase, "
               "including when a competing commit occurs after preview. Generated status/index edits require "
               "a separately authored proposal and never change scientific disposition or operating policy.\n\n")
        for row in prior.to_dict()["mappings"]:
            yield from _literal(row)
        yield "## Actual preserved files\n\n"
        for row in preservation["files"]:
            yield from _literal(row)
            yield "[Preserved bytes](" + quote("preservation/" + row["preservation_path"], safe="/") + ")\n\n"
    budget, chunks = _Metadata(maximum), []
    for chunk in parts():
        data = chunk.encode("utf-8")
        budget.reserve(len(data))
        chunks.append(data)
    return b"".join(chunks)


def _package_metadata(capture, preservation, prior, successor, limits):
    """Build deterministic controls and count each serialized control/copy once before reservation."""
    selection, records = _relationships(prior, successor, limits.max_diagnostics)
    diagnostics = len(records) + sum(len(preservation[k]) for k in
        ("comparisons", "rename_groups", "missing", "target_diagnostics"))
    if diagnostics > limits.max_diagnostics:
        raise SnapshotLimitError("max_diagnostics exceeded")
    controls = {"capture.json": _bounded_json(capture, limits.max_metadata_bytes, "capture metadata").encode("ascii"),
                "preservation-plan.json": _bounded_json(preservation, limits.max_metadata_bytes, "preservation metadata").encode("ascii")}
    controls["README.md"] = _report(capture, preservation, prior, successor, selection, records,
                                    limits.max_metadata_bytes)
    files = [dict(path=p, sha256=_digest(data), size=len(data), mode=0o400) for p, data in controls.items()]
    files.extend(dict(path="preservation/" + r["preservation_path"], sha256=r["sha256"], size=r["size"], mode=0o600)
                 for r in preservation["files"])
    files.extend(dict(path="generation/" + e.relative_path, sha256=_digest(e.data), size=len(e.data), mode=0o400)
                 for e in successor.generated_files)
    files.extend(dict(path="generation/" + e.relative_path, sha256=e.digest, size=e.size, mode=0o400)
                 for e in successor.artifact_copies)
    directories = [dict(path="", mode=0o500)]
    directories.extend(dict(path="preservation" + ("/" + r["preservation_path"] if r["preservation_path"] else ""),
                            mode=0o700) for r in preservation["directories"])
    directories.extend(dict(path="generation" + ("/" + e.relative_path if e.relative_path else ""), mode=0o500)
                       for e in successor.directories)
    document = dict(format="research_pipeline.readable_refresh", version=1, refresh_id="0" * 64,
        prior=dict(path=capture["prior_view"], snapshot_id=prior.snapshot_id, plan_id=prior.plan_id,
                   manifest_sha256=_digest(prior.manifest_bytes)),
        successor=dict(path="generation", snapshot_id=successor.snapshot_id, plan_id=successor.plan_id,
                       manifest_sha256=_digest(successor.manifest_bytes)),
        capture=dict(path="capture.json", capture_id=capture["capture_id"], sha256=_digest(controls["capture.json"]),
                     size=len(controls["capture.json"])),
        preservation=dict(path="preservation", plan_path="preservation-plan.json",
            preservation_plan_id=preservation["preservation_plan_id"], sha256=_digest(controls["preservation-plan.json"]),
            size=len(controls["preservation-plan.json"]), status="unsubmitted_proposed_work"),
        same_plan=prior.plan_id == successor.plan_id, selection=selection, records=records,
        files=sorted(files, key=lambda r: r["path"]), directories=sorted(directories, key=lambda r: r["path"]),
        descriptor=dict(path="refresh.json", mode=0o400, self_excluded=True), limitations=list(LIMITATIONS))
    _bounded_json(document, limits.max_metadata_bytes, "refresh metadata preflight")
    document["refresh_id"] = _identified(document, "refresh_id")
    controls["refresh.json"] = _bounded_json(document, limits.max_metadata_bytes, "refresh metadata").encode("ascii")
    # The embedded expected manifest is already included in capture.json. Opaque
    # observed evidence has its actual size, even when it is not parseable JSON.
    metadata_size = (sum(len(data) for data in controls.values()) + len(successor.manifest_bytes)
                     + sum(row["size"] for row in preservation["files"]
                           if row["preservation_path"] in
                           ("controls/expected-manifest.json", "controls/observed-manifest.bin")))
    if metadata_size > limits.max_metadata_bytes:
        raise SnapshotLimitError("aggregate refresh metadata exceeds max_metadata_bytes")
    return document, controls, metadata_size
