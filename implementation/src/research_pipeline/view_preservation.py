"""Pure deterministic preservation proposals over fully detached readable-view captures."""

from dataclasses import dataclass
import posixpath

from research_pipeline.domain import DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError, _bounded_json, _canonical
from research_pipeline.vault import ViewIntegrityError
from research_pipeline.view_capture import (
    CapturedReadableView, _Metadata, _digest, _expected, _identified, _validated_capture,
)
from research_pipeline.view_plan import _literal


_FORMAT = "research_pipeline.readable_preservation_plan"
_LIMITATIONS = (
    "Unsubmitted proposed work; planning only, with no durable preservation or successor.",
    "Canonical records, historical paths and scientific authority remain unchanged.",
    "Exact-path associations identify the prior occupant, not authenticated historical edited bytes.",
    "No scientific endorsement, automatic import, execution, configuration or policy activation.",
    "Prior generated links were mechanically verified; authored and observed edited links are not certified or repaired.",
    "Future output files require mode 0600 and directories mode 0700; source execute bits confer no authority.",
)


def _entries(files, directories):
    """Index exact inventory paths with explicit kind, retaining original expected/observed fields."""
    return {**{row["path"]: {**row, "kind": "file"} for row in files},
            **{row["path"]: {**row, "kind": "directory"} for row in directories}}


def _subtrees(entries):
    """Hash complete ordered relative subtree structure, ignoring modes for separate diagnosis.

    Each directory digest binds every immediate name, kind and recursive child
    digest; file nodes bind hash and size. Thus all descendant suffixes participate
    without materializing a quadratic list of paths for every possible ancestor.
    """
    children = {path: [] for path, row in entries.items() if row["kind"] == "directory"}
    for path, row in entries.items():
        if path:
            children[posixpath.dirname(path)].append(path)
    digests = {}
    for path in sorted(children, key=lambda p: (p.count("/") + bool(p), p), reverse=True):
        values = []
        for child in sorted(children[path]):
            row = entries[child]
            value = [posixpath.basename(child), row["kind"]]
            value.extend([row["sha256"], row["size"]] if row["kind"] == "file" else [digests[child]])
            values.append(value)
        digests[path] = _digest(_canonical(values).encode("ascii"))
    return {path: digest for path, digest in digests.items() if path and children[path]}


def _under(path, parent):
    """Test exact component containment without confusing sibling prefixes."""
    return path == parent or path.startswith(parent + "/")


def _group(basis, expected, observed, ambiguous):
    """Create a stable compact identity group, never a Cartesian list of speculative owners."""
    value = dict(basis=basis, expected_paths=sorted(expected), observed_paths=sorted(observed), ambiguous=ambiguous)
    return {"group_id": _digest(_canonical(value).encode("ascii")), **value}


class _Planning:
    """One bounded pure comparison; canonical path references preserve original manifest associations."""

    def __init__(self, state_size, document, plan, limits):
        """Reserve retained capture/control metadata and prepare exact independent inventories."""
        self.state_size, self.document, self.plan, self.limits = state_size, document, plan, limits
        files, directories = _expected(plan, limits)
        self.expected = _entries(files, directories)
        self.observed = _entries(document["files"], document["directories"])
        self.result = dict(format=_FORMAT, version=1, preservation_plan_id="0" * 64,
            capture_id=document["capture_id"], expected_plan_id=plan.plan_id, status="planned_only",
            files=[], directories=[], comparisons=[], rename_groups=[], missing=[], target_diagnostics=[],
            explanation="", limitations=list(_LIMITATIONS))
        self.budget = _Metadata(limits.max_metadata_bytes, state_size + len(plan.manifest_bytes))
        self.budget.reserve(self.budget.size(self.result))
        self.diagnostics = 0
        self.matches, self.groups, self.matched_observed = {}, {}, set()

    def append(self, name, row, *, diagnostic=False):
        """Charge a complete row before retaining it; never truncate diagnostic evidence."""
        if diagnostic:
            if self.diagnostics >= self.limits.max_diagnostics:
                raise SnapshotLimitError("max_diagnostics exceeded")
            self.diagnostics += 1
        self.budget.append(self.result[name], row)

    def group(self, basis, expected, observed, ambiguous):
        """Retain one deterministic shared candidate group and return its stable reference."""
        row = _group(basis, expected, observed, ambiguous)
        self.append("rename_groups", row, diagnostic=True)
        return row["group_id"]

    def directory_moves(self):
        """Select maximal non-overlapping unique complete subtree correspondences."""
        old, new = {}, {}
        for path, digest in _subtrees(self.expected).items():
            old.setdefault(digest, []).append(path)
        for path, digest in _subtrees(self.observed).items():
            new.setdefault(digest, []).append(path)
        candidates = []
        for digest, paths in old.items():
            others = new.get(digest, [])
            if len(paths) == len(others) == 1:
                source, target = paths[0], others[0]
                if source not in self.observed and target not in self.expected:
                    candidates.append((source, target))
        selected = []
        for source, target in sorted(candidates, key=lambda pair: (pair[0].count("/"), pair)):
            if any(_under(source, old_path) or _under(target, new_path) for old_path, new_path in selected):
                continue
            group = self.group("exact_subtree", [source], [target], False)
            selected.append((source, target))
            for path in sorted(self.expected):
                if _under(path, source):
                    observed = target + path[len(source):]
                    self.matches[path] = (observed, "exact_subtree", group)
                    self.matched_observed.add(observed)

    def file_moves(self):
        """Use all byte owners/occurrences; unrelated copies prevent unjustified rename identity."""
        expected, observed = {}, {}
        for path, row in self.expected.items():
            if row["kind"] == "file":
                expected.setdefault((row["sha256"], row["size"]), []).append(path)
        for path, row in self.observed.items():
            if row["kind"] == "file":
                observed.setdefault((row["sha256"], row["size"]), []).append(path)
        for identity in sorted(expected):
            owners, occurrences = sorted(expected[identity]), sorted(observed.get(identity, []))
            missing = [p for p in owners if p not in self.observed and p not in self.matches]
            extras = [p for p in occurrences if p not in self.expected and p not in self.matched_observed]
            # Swaps and replacements also retain candidate evidence, while exact
            # paths retain their own occupant association rather than adopting it.
            changed_occurrences = [p for p in occurrences if p in self.expected and
                (self.expected[p]["kind"] != "file" or
                 (self.expected[p]["sha256"], self.expected[p]["size"]) != identity)]
            if len(owners) == len(occurrences) == 1 and missing and extras:
                group = self.group("exact_bytes", owners, occurrences, False)
                self.matches[missing[0]] = (extras[0], "exact_bytes", group)
                self.matched_observed.add(extras[0])
            elif occurrences and (missing or extras or changed_occurrences):
                group = self.group("exact_bytes", owners, occurrences, True)
                for path in owners:
                    if path not in self.matches:
                        self.groups.setdefault(("expected", path), []).append(group)
                for path in occurrences:
                    if path not in self.matched_observed:
                        self.groups.setdefault(("observed", path), []).append(group)

    def comparison(self, expected_path, observed_path, basis, group=None):
        """Compare separate byte/mode identities; exact-path edits remain path-based proposed content."""
        expected = self.expected.get(expected_path)
        observed = self.observed.get(observed_path)
        codes = []
        if expected is None:
            codes.append("added_unresolved")
        elif observed is None:
            codes.append("missing")
        else:
            if expected_path != observed_path:
                codes.append("renamed")
            if expected["kind"] != observed["kind"]:
                codes.append("type_changed")
            elif expected["kind"] == "file" and (expected["sha256"], expected["size"]) != (observed["sha256"], observed["size"]):
                codes.append("content_changed")
            if expected["mode"] != observed["mode"]:
                codes.append("mode_changed")
        candidate_groups = set(self.groups.get(("expected", expected_path), []))
        candidate_groups.update(self.groups.get(("observed", observed_path), []))
        if candidate_groups:
            codes.append("ambiguous")
        # One row can reference multiple compact byte groups in swaps. The schema
        # uses null or a sorted list of group IDs for this explicit reference.
        references = sorted(candidate_groups | ({group} if group else set()))
        row = dict(expected_path=expected_path, expected_kind=expected["kind"] if expected else None,
            expected_sha256=expected.get("sha256") if expected else None,
            expected_size=expected.get("size") if expected else None,
            expected_mode=expected["mode"] if expected else None,
            observed_path=observed_path, observed_kind=observed["kind"] if observed else None,
            observed_sha256=observed.get("sha256") if observed else None,
            observed_size=observed.get("size") if observed else None,
            observed_mode=observed["mode"] if observed else None, codes=sorted(codes),
            association_basis=basis, rename_group=references or None)
        self.append("comparisons", row, diagnostic=True)
        return row

    def comparisons(self):
        """Report every canonical entry and every unmatched observed entry in path order."""
        used = set()
        for path in sorted(self.expected):
            if path in self.observed:
                target, basis, group = path, "exact_path", None
            else:
                target, basis, group = self.matches.get(path, (None, "unresolved", None))
            self.comparison(path, target, basis, group)
            if target is not None:
                used.add(target)
            if path not in self.observed:
                parent = posixpath.dirname(path)
                blocked = None
                while parent:
                    if parent in self.observed and self.observed[parent]["kind"] != "directory":
                        blocked = parent
                        break
                    parent = posixpath.dirname(parent)
                self.append("missing", dict(expected_path=path, expected_kind=self.expected[path]["kind"],
                                             blocked_ancestor=blocked), diagnostic=True)
        for path in sorted(set(self.observed) - used):
            self.comparison(None, path, "unresolved")

    def copies(self):
        """Account once for every divergent file and meaningful directory, plus separate controls."""
        reasons, directory_reasons = {}, {}
        for row in self.result["comparisons"]:
            if row["observed_path"] is not None and row["codes"]:
                target = reasons if row["observed_kind"] == "file" else directory_reasons
                target.setdefault(row["observed_path"], set()).update(row["codes"])
        # Every file in a safely substituted directory is proposed work even if a
        # future inventory format were to give one of its descendants an exact match.
        substitutions = [r["observed_path"] for r in self.result["comparisons"]
                         if "type_changed" in r["codes"] and r["observed_kind"] == "directory"]
        for path, row in self.observed.items():
            if row["kind"] == "file" and any(_under(path, parent) for parent in substitutions):
                reasons.setdefault(path, set()).add("type_changed")
        control = dict(source_path=None, preservation_path="controls/expected-manifest.json",
                       sha256=self.document["expected_manifest_sha256"], size=len(self.plan.manifest_bytes),
                       reasons=["independent_expected_manifest"])
        self.append("files", control)
        manifest = self.observed.get("manifest.json")
        if manifest and manifest["kind"] == "file":
            self.append("files", dict(source_path="manifest.json", preservation_path="controls/observed-manifest.bin",
                sha256=manifest["sha256"], size=manifest["size"],
                reasons=sorted({"observed_manifest"} | reasons.pop("manifest.json", set()))))
        for path in sorted(reasons):
            row = self.observed[path]
            self.append("files", dict(source_path=path, preservation_path="tree/" + path,
                sha256=row["sha256"], size=row["size"], reasons=sorted(reasons[path])))
        required = {"": (None, None, {"output_root"}), "controls": (None, None, {"control_evidence"})}
        for path, codes in directory_reasons.items():
            required["tree" + ("/" + path if path else "")] = (path, self.observed[path]["mode"], codes)
        for row in self.result["files"]:
            parent = posixpath.dirname(row["preservation_path"])
            while parent and parent not in required:
                source = parent.removeprefix("tree/") if parent.startswith("tree/") else "" if parent == "tree" else None
                original = self.observed.get(source)
                required[parent] = (source, original["mode"] if original else None, {"required_parent"})
                parent = posixpath.dirname(parent)
        # Added/moved empty directories still need their own complete ancestor chain.
        for path in list(required):
            parent = posixpath.dirname(path)
            while parent and parent not in required:
                source = parent.removeprefix("tree/") if parent.startswith("tree/") else "" if parent == "tree" else None
                original = self.observed.get(source)
                required[parent] = (source, original["mode"] if original else None, {"required_parent"})
                parent = posixpath.dirname(parent)
        for path, (source, mode, codes) in sorted(required.items()):
            self.append("directories", dict(source_path=source, preservation_path=path,
                                           observed_mode=mode, mode=0o700, reasons=sorted(codes)))
        self.result["files"].sort(key=lambda row: row["preservation_path"])

    def targets(self):
        """Diagnose all missing/moved/type-changed/ambiguous canonical targets via original path refs."""
        copies = {row["source_path"]: row["preservation_path"] for row in self.result["files"]}
        directories = {row["source_path"]: row["preservation_path"] for row in self.result["directories"]}
        for row in self.result["comparisons"]:
            codes = sorted(set(row["codes"]) & {"missing", "renamed", "type_changed", "ambiguous"})
            if row["expected_path"] is not None and codes:
                path = row["observed_path"]
                preserved = copies.get(path) if row["observed_kind"] == "file" else directories.get(path)
                self.append("target_diagnostics", dict(expected_path=row["expected_path"],
                    observed_path=path, preservation_path=preserved if path is not None else None,
                    rename_group=row["rename_group"], codes=codes), diagnostic=True)

    def explain(self):
        """Render bounded inert identities and unresolved evidence without interpreting authored content."""
        # Fixed headings and literal JSON escape even control-looking supplied paths.
        values = [("Prior snapshot", self.plan.snapshot_id), ("Prior plan", self.plan.plan_id),
                  ("Capture", self.document["capture_id"]), ("Prior location", self.document["prior_view"])]
        changed = sum(bool(row["codes"]) for row in self.result["comparisons"])
        values.extend((("Changed comparison rows", changed), ("Missing original paths", len(self.result["missing"])),
                       ("Unresolved byte groups", sum(g["ambiguous"] for g in self.result["rename_groups"]))))
        def parts():
            """Yield fixed prose and bounded literal chunks before any explanation allocation."""
            yield "# Readable preservation plan\n\n"
            for line in _LIMITATIONS:
                yield line + "\n\n"
            if self.result["missing"] and any("added_unresolved" in r["codes"] for r in self.result["comparisons"]):
                yield ("Rename-plus-edit cannot be resolved automatically. Missing-target evidence and exact added "
                       "bytes remain available for manual mapping.\n\n")
            for label, value in values:
                yield label + ":\n\n"
                yield from _literal(value)

        chunks = []
        for chunk in parts():
            # The empty explanation's two JSON quotes were reserved in the base
            # document. Count content escaping plus the standalone readable copy.
            self.budget.reserve(len(chunk.encode("utf-8")))
            encoded = _bounded_json(chunk, self.budget.maximum - self.budget.used + 2, "explanation")
            self.budget.reserve(len(encoded) - 2)
            chunks.append(chunk)
        self.result["explanation"] = "".join(chunks)

    def finish(self):
        """Return a complete deterministic plan after exact aggregate metadata accounting."""
        self.directory_moves()
        self.file_moves()
        self.comparisons()
        self.copies()
        self.targets()
        self.explain()
        self.result["rename_groups"].sort(key=lambda row: row["group_id"])
        self.result["preservation_plan_id"] = _identified(self.result, "preservation_plan_id")
        maximum = self.limits.max_metadata_bytes - self.state_size - len(self.plan.manifest_bytes)
        maximum -= len(self.result["explanation"].encode("utf-8"))
        _bounded_json(self.result, maximum, "aggregate preservation metadata")
        return self.result


def _build(capture):
    """Validate detached inputs and derive one complete plan with no filesystem or store reads."""
    document, plan, limits = _validated_capture(capture)
    return _plan_metadata(document, plan, limits, len(capture._state))


def _plan_metadata(document, plan, limits, state_size):
    """Derive exact preservation from validated metadata and its independent canonical plan."""
    return _Planning(state_size, document, plan, limits).finish()


@dataclass(frozen=True, init=False)
class ReadablePreservationPlan:
    """Immutable planned-only metadata; retained capture supplies exact bytes and original mappings."""

    _state: str
    _capture: CapturedReadableView

    def __init__(self, capture):
        """Build strict deterministic metadata from a validated capture without publishing anything."""
        result = _build(capture)
        # Detach even the private frozen object so bypassing the caller's fields
        # cannot silently alter this plan's source association.
        detached = CapturedReadableView(capture.to_dict(), capture._payloads, capture._limits)
        object.__setattr__(self, "_capture", detached)
        object.__setattr__(self, "_state", _canonical(result))

    def to_dict(self):
        """Rebuild and compare exact schema, IDs and cross-references before returning fresh metadata."""
        expected = _build(self._capture)
        if type(self._state) is not str or self._state != _canonical(expected):
            raise ViewIntegrityError("retained preservation metadata differs from deterministic plan")
        return expected

    @property
    def preservation_plan_id(self):
        """Return the validated planned-only identity, not a publication receipt."""
        return self.to_dict()["preservation_plan_id"]

    @property
    def capture_id(self):
        """Return the exact local observation to which this proposal refers."""
        return self.to_dict()["capture_id"]

    @property
    def explanation(self):
        """Return the bounded inert readable explanation after full retained-state validation."""
        return self.to_dict()["explanation"]


def plan_readable_preservation(capture: CapturedReadableView) -> ReadablePreservationPlan:
    """Plan exact independent copies and honest identity/path diagnostics entirely offline.

    No files are created, imported, repaired or activated. Canonical expected-path
    references point to the complete retained manifest, including generated roles,
    record page/envelope relationships and every original artifact mapping.
    """
    if type(capture) is not CapturedReadableView:
        raise DomainValidationError("capture: expected CapturedReadableView")
    return ReadablePreservationPlan(capture)
