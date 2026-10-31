"""Strict metadata-only refresh descriptor checks, including unfinished preparations."""

import posixpath
import stat

from research_pipeline.domain import ArtifactReference, _integer, _identifier
from research_pipeline.snapshot import RootSelector, SnapshotSelection, SnapshotLimitError, _canonical
from research_pipeline.vault import ViewIntegrityError
from research_pipeline.view_capture import _fields, _identified, _digest
from research_pipeline.view_refresh_metadata import LIMITATIONS


def _selection(value):
    """Validate requested roots and matching positive resolutions without consulting live heads."""
    _fields(value, ("prior_requested", "prior_resolutions", "successor_requested", "successor_resolutions"), "selection")
    for side in ("prior", "successor"):
        requested, resolutions = value[side + "_requested"], value[side + "_resolutions"]
        _fields(requested, ("project", "roots"), "requested selection")
        if type(requested["roots"]) is not list or type(resolutions) is not list:
            raise ViewIntegrityError("selection arrays required")
        selectors = []
        for row in [requested["project"], *requested["roots"]]:
            _fields(row, ("record_id", "revision"), "selector")
            selectors.append(RootSelector(**row))
        SnapshotSelection(selectors[0], tuple(selectors[1:]))
        if len(selectors) != len(resolutions):
            raise ViewIntegrityError("resolution count mismatch")
        for selector, row in zip(selectors, resolutions):
            _fields(row, ("record_id", "revision"), "resolution")
            RootSelector(**row)
            _integer(row["revision"], "resolved revision", 1)
            if row["record_id"] != selector.record_id or selector.revision not in (None, row["revision"]):
                raise ViewIntegrityError("resolution disagrees with requested root")
    if value["prior_requested"]["project"]["record_id"] != value["successor_requested"]["project"]["record_id"]:
        raise ViewIntegrityError("refresh selection changes project")


def _refresh_control(value, data, intent, reader, limits):
    """Validate exact v1 structure/identity and every present referenced file; allow unwritten files.

    Full deterministic reconstruction remains necessary for completion. This gate
    independently rejects malformed controls even before the successor exists.
    """
    _fields(value, ("format", "version", "refresh_id", "prior", "successor", "capture", "preservation",
                   "same_plan", "selection", "records", "files", "directories", "descriptor", "limitations"), "refresh")
    if (value["format"] != "research_pipeline.readable_refresh" or type(value["version"]) is not int
            or value["version"] != 1 or value["limitations"] != list(LIMITATIONS)
            or type(value["same_plan"]) is not bool):
        raise ViewIntegrityError("unsupported refresh schema")
    for side in ("prior", "successor"):
        row = value[side]
        _fields(row, ("path", "snapshot_id", "plan_id", "manifest_sha256"), side)
        for key in ("snapshot_id", "plan_id", "manifest_sha256"):
            ArtifactReference(row[key], 0)
        if row["plan_id"] != intent[side + "_plan_id"]:
            raise ViewIntegrityError("refresh plan differs from intent")
    from research_pipeline.checkout import _path
    prior_path = value["prior"]["path"]
    if type(prior_path) is not str or not prior_path.startswith("/") or str(_path(prior_path)) != prior_path:
        raise ViewIntegrityError("invalid prior path")
    if value["successor"]["path"] != "generation":
        raise ViewIntegrityError("invalid successor location")
    if value["same_plan"] != (value["prior"]["plan_id"] == value["successor"]["plan_id"]):
        raise ViewIntegrityError("contradictory same-plan flag")
    _fields(value["capture"], ("path", "capture_id", "sha256", "size"), "capture reference")
    _fields(value["preservation"], ("path", "plan_path", "preservation_plan_id", "sha256", "size", "status"), "preservation reference")
    if (value["capture"]["path"] != "capture.json" or value["preservation"]["path"] != "preservation"
            or value["preservation"]["plan_path"] != "preservation-plan.json"
            or value["preservation"]["status"] != "unsubmitted_proposed_work"):
        raise ViewIntegrityError("invalid capture/preservation locations/status")
    for side, key in (("capture", "capture_id"), ("preservation", "preservation_plan_id")):
        row = value[side]
        ArtifactReference(row["sha256"], row["size"])
        ArtifactReference(row[key], 0)
        if row[key] != intent[key]:
            raise ViewIntegrityError("refresh association differs from intent")
    if (value["refresh_id"] != _identified(value, "refresh_id") or value["refresh_id"] != intent["refresh_id"]
            or _digest(data) != intent["manifest_sha256"]):
        raise ViewIntegrityError("refresh identity/hash differs from intent")
    if _canonical(value["descriptor"]) != _canonical(dict(path="refresh.json", mode=0o400, self_excluded=True)):
        raise ViewIntegrityError("invalid descriptor reference")
    _selection(value["selection"])
    inventories = _inventory(value, limits)
    _references(value, inventories, reader)
    _records(value, inventories, limits)
    return value


def _inventory(value, limits):
    """Require sorted unique safe inventory paths, fixed modes and complete declared parent chains."""
    from research_pipeline.view_refresh import _relative, _inventory_bounds
    inventories, aliases = {}, {}
    for kind in ("files", "directories"):
        rows = value[kind]
        if type(rows) is not list:
            raise ViewIntegrityError("inventory array required")
        paths = []
        for row in rows:
            _fields(row, ("path", "sha256", "size", "mode") if kind == "files" else ("path", "mode"), kind)
            path = row["path"]
            if type(path) is not str:
                raise ViewIntegrityError("inventory path must be text")
            key = _relative(path, limits)
            if kind == "files":
                permitted = (path in ("capture.json", "preservation-plan.json", "README.md")
                             or path.startswith("generation/") or path.startswith("preservation/tree/")
                             or path in ("preservation/controls/expected-manifest.json",
                                         "preservation/controls/observed-manifest.bin"))
            else:
                permitted = (path in ("", "generation", "preservation", "preservation/controls", "preservation/tree")
                             or path.startswith("generation/") or path.startswith("preservation/tree/"))
            if not permitted:
                raise ViewIntegrityError("unexpected refresh inventory location")
            if path in inventories or key in aliases:
                raise ViewIntegrityError("duplicate/aliased refresh inventory")
            aliases[key], inventories[path] = path, (kind, row)
            paths.append(path)
            expected_mode = 0o600 if path.startswith("preservation/") else 0o400
            if kind == "directories":
                expected_mode = 0o700 if path == "preservation" or path.startswith("preservation/") else 0o500
            if type(row["mode"]) is not int or row["mode"] != expected_mode:
                raise ViewIntegrityError("invalid inventory mode")
            if kind == "files":
                ArtifactReference(row["sha256"], row["size"])
                if not path or path == "refresh.json":
                    raise ViewIntegrityError("invalid inventory file")
        if paths != sorted(paths):
            raise ViewIntegrityError("unsorted inventory")
    if inventories.get("", (None,))[0] != "directories":
        raise ViewIntegrityError("missing package root")
    for path in ("capture.json", "preservation-plan.json", "README.md", "generation/manifest.json",
                 "preservation/controls/expected-manifest.json"):
        if inventories.get(path, (None,))[0] != "files":
            raise ViewIntegrityError("missing declared package control")
    for path in inventories:
        if path and inventories.get(posixpath.dirname(path), (None,))[0] != "directories":
            raise ViewIntegrityError("missing inventory directory parent")
    _inventory_bounds(value["files"], value["directories"], limits)
    return inventories


def _references(value, inventories, reader):
    """Bind descriptor references and present stage bytes/modes without requiring future files."""
    for side, path in (("capture", "capture.json"), ("preservation", "preservation-plan.json")):
        row = inventories.get(path, (None, {}))[1]
        if any(row.get(k) != value[side][k] for k in ("sha256", "size")):
            raise ViewIntegrityError("control reference differs from inventory")
    for side, path in (("prior", "preservation/controls/expected-manifest.json"), ("successor", "generation/manifest.json")):
        if inventories.get(path, (None, {}))[1].get("sha256") != value[side]["manifest_sha256"]:
            raise ViewIntegrityError("manifest reference differs from inventory")
    for key, pin in reader.pins.items():
        if not key.startswith("package/"):
            continue
        path = key.removeprefix("package/")
        if path == "refresh.json":
            if stat.S_IMODE(pin[3].st_mode) != 0o400:
                raise ViewIntegrityError("invalid descriptor mode")
            continue
        kind, row = inventories.get(path, (None, {}))
        if (kind != "files" or (pin[4].digest, pin[4].size, stat.S_IMODE(pin[3].st_mode))
                != (row.get("sha256"), row.get("size"), row.get("mode"))):
            raise ViewIntegrityError("present file differs from refresh inventory")
    for key, mode in reader.modes.items():
        if key == "package" or key.startswith("package/"):
            path = "" if key == "package" else key.removeprefix("package/")
            kind, row = inventories.get(path, (None, {}))
            if kind != "directories" or mode not in (row.get("mode"), 0o700):
                raise ViewIntegrityError("present directory differs from refresh inventory")


def _records(value, inventories, limits):
    """Validate exact record mappings and root ordinals against both declared selections."""
    from research_pipeline.view_refresh import _relative
    if type(value["records"]) is not list:
        raise ViewIntegrityError("record mappings array required")
    if len(value["records"]) > limits.max_diagnostics:
        raise SnapshotLimitError("max_diagnostics exceeded by record mappings")
    keys = []
    for row in value["records"]:
        _fields(row, ("record_id", "revision", "prior_page_path", "successor_page_path",
                      "prior_root_ordinals", "successor_root_ordinals"), "record mapping")
        _identifier(row["record_id"], "record_id")
        _integer(row["revision"], "revision", 1)
        key = row["record_id"], row["revision"]
        keys.append(key)
        if row["prior_page_path"] is None and row["successor_page_path"] is None:
            raise ViewIntegrityError("record mapping has no owner")
        for side in ("prior", "successor"):
            path, ordinals = row[side + "_page_path"], row[side + "_root_ordinals"]
            if path is not None:
                if type(path) is not str or not path:
                    raise ViewIntegrityError("empty record page path")
                _relative(path, limits)
                if side == "successor" and inventories.get("generation/" + path, (None,))[0] != "files":
                    raise ViewIntegrityError("successor mapping references absent page")
            if type(ordinals) is not list or any(type(i) is not int or i < 0 for i in ordinals):
                raise ViewIntegrityError("invalid root ordinals")
            expected = [i for i, pin in enumerate(value["selection"][side + "_resolutions"])
                        if (pin["record_id"], pin["revision"]) == key]
            if ordinals != expected or path is None and ordinals:
                raise ViewIntegrityError("root ordinals disagree with mapping")
    if keys != sorted(set(keys)):
        raise ViewIntegrityError("noncanonical record mapping order")
    for side in ("prior", "successor"):
        if any((pin["record_id"], pin["revision"]) not in keys for pin in value["selection"][side + "_resolutions"]):
            raise ViewIntegrityError("root missing from record mappings")
