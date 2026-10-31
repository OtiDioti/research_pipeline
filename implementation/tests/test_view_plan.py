"""Pure offline projections, portable inert inventory and independently enumerated navigation evidence."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline.corpus import encode_envelope as corpus_envelope
from research_pipeline.domain import CreationProvenance, RecordEnvelope, RecordReference
from research_pipeline.project import encode_envelope as project_envelope
from research_pipeline.snapshot import DetachedSnapshot, RootSelector, SnapshotSelection, SnapshotLimitError, _canonical
from research_pipeline.store import RecordStore
from research_pipeline.view_plan import (
    ArtifactCopy, DirectoryEntry, GeneratedFile, ReadablePlan, ViewPlanError,
    plan_readable_snapshot, verify_plan_links,
)
from research_pipeline.work_product import encode_envelope as product_envelope
from tests.snapshot_fixtures import HOSTILE, limits, selection, simple_project, populated
from tests.test_corpus import inventory, entry
from tests.test_project import setup
from research_pipeline.source import decode_envelope as decode_source
from tests.test_store import CREATOR, record, request
from tests.test_typed_store import ref
from tests.test_work_product import manifest
from tests.test_source import source, uninspected
from research_pipeline.source import encode_envelope as source_envelope


README_FIELDS = {"Purpose and scope", "Contents", "Current work", "Provenance", "Use",
                 "Dependencies and limitations", "Editing route"}


def emitted_navigation(plan):
    """Independently enumerate actual generated links/headings, excluding inert literal code and YAML."""
    pages, graph = {}, {}
    for file in plan.generated_files:
        if not file.relative_path.endswith(".md"):
            continue
        lines = file.data.decode("utf-8").splitlines()
        if lines and lines[0] == "---":
            lines = lines[lines.index("---", 1) + 1:]
        prose = "\n".join(line for line in lines if not line.startswith("    "))
        headings = re.findall(r"^#{1,6} (.+)$", prose, re.MULTILINE)
        pages[file.relative_path] = headings
        graph[file.relative_path] = []
        for destination in re.findall(r"\[[^\[\]\n]*\]\(([^)]+)\)", prose):
            path, _, fragment = destination.partition("#")
            target = posixpath.normpath(posixpath.join(posixpath.dirname(file.relative_path), path)) if path else file.relative_path
            graph[file.relative_path].append((target, fragment))
    return pages, graph


def forged_plan(plan, replacements):
    """Rehash deliberate generated-page defects so link verification, rather than stale identity, rejects them."""
    generated = tuple(replace(f, data=replacements.get(f.relative_path, f.data)) for f in plan.generated_files
                      if f.relative_path != "manifest.json")
    manifest = plan.to_dict()
    by_path = {f.relative_path: f for f in generated}
    for entry in manifest["files"]:
        if entry["path"] in by_path:
            data = by_path[entry["path"]].data
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            entry["size"] = len(data)
    del manifest["plan_id"]
    identity = hashlib.sha256(_canonical(manifest).encode("ascii")).hexdigest()
    manifest["plan_id"] = identity
    data = _canonical(manifest).encode("ascii")
    value = object.__new__(ReadablePlan)
    for name, item in (("snapshot_id", plan.snapshot_id), ("plan_id", identity),
                       ("generated_files", tuple(sorted((*generated, GeneratedFile("manifest.json", data, "manifest")), key=lambda f: f.relative_path))),
                       ("artifact_copies", plan.artifact_copies), ("directories", plan.directories), ("manifest_bytes", data)):
        object.__setattr__(value, name, item)
    return value


class DetachedProjectionTests(unittest.TestCase):
    """Exercise detached projection consistency independently of real-file Source acquisition fixtures."""

    def test_reference_shaped_provenance_remains_literal(self):
        """Arbitrary reference lookalikes preserve JSON types without links; real envelope edges still navigate."""
        lookalikes = (
            {"record_id": [], "revision": 1, "relationship": "description"},
            {"record_id": {}, "revision": 1, "relationship": "description"},
            {"record_id": "context", "revision": [], "relationship": "description"},
            {"record_id": "context", "revision": {}, "relationship": "description"},
            {"record_id": "context", "revision": True, "relationship": "description"},
            RecordReference("context", 1, "description", "research_context").to_dict(),
        )
        for index, lookalike in enumerate(lookalikes):
            for nested in (False, True):
                with self.subTest(case=index, nested=nested), TemporaryDirectory(prefix="literal-provenance-") as temporary:
                    details = {"nested": [{"description": lookalike}]} if nested else lookalike
                    provenance = CreationProvenance("author", "2026-10-30T10:00:00Z", details)
                    with RecordStore.create(Path(temporary) / "runtime") as store:
                        artifact = store.put_artifact(b"Provenance mapping regression.\n")
                        store.submit(request("descriptive", [record("project", kind="project", provenance=provenance,
                            record_references=[RecordReference("context", 1, "description", "research_context")],
                            artifact_references=[artifact]), record()]))
                        snapshot = store.capture_snapshot(selection(), limits=limits())
                    plan = plan_readable_snapshot(snapshot)
                    rebuilt = ReadablePlan(plan.snapshot_id, plan.plan_id, plan.generated_files,
                                           plan.artifact_copies, plan.directories, plan.manifest_bytes)
                    manifest = rebuilt.to_dict()
                    verify_plan_links(rebuilt)
                    records = {item["record_id"]: item for item in manifest["records"]}
                    page = records["project"]["page_path"]
                    files = {file.relative_path: file.data for file in rebuilt.generated_files}
                    companion = files[page].decode()
                    section = companion.split("## Provenance\n\n", 1)[1].split("## Use\n", 1)[0]
                    self.assertNotRegex(section, r"\[[^\[\]\n]*\]\([^)]+\)")
                    outgoing = companion.split("## Exact outgoing relationships\n\n", 1)[1].split("\n## ", 1)[0]
                    relative = posixpath.relpath(records["context"]["page_path"], posixpath.dirname(page))
                    self.assertIn("Edge 0: description", outgoing)
                    self.assertIn("[context&#64;1](" + relative + ")", outgoing)
                    _, graph = emitted_navigation(rebuilt)
                    self.assertIn((records["context"]["page_path"], ""), graph[page])
                    expected = _canonical(provenance.to_dict())
                    raw_path = posixpath.dirname(page) + "/envelope.json"
                    self.assertEqual(_canonical(json.loads(files[raw_path])["provenance"]), expected)
                    self.assertEqual(_canonical(json.loads(records["project"]["envelope_json"])["provenance"]), expected)
                    self.assertEqual(records["project"]["provenance_json"], expected)
                    self.assertEqual(len(manifest["mappings"]), 1)
                    self.assertEqual(len(manifest["artifacts"][0]["mappings"]), 1)
                    for mapping in (*manifest["mappings"], *manifest["artifacts"][0]["mappings"]):
                        self.assertEqual(_canonical(mapping["provenance"]), expected)

    def test_depth_64_provenance_with_attachment_round_trips(self):
        """Boundary-valid provenance survives closed-store reconstruction and all five manifest wrappers."""
        value = 0
        for _ in range(62):
            value = [value]
        # Provenance and details objects add two levels to the 62 nested lists.
        provenance = CreationProvenance("author", "2026-10-30T10:00:00Z", {"nested": value})
        with TemporaryDirectory(prefix="deep-provenance-") as temporary:
            with RecordStore.create(Path(temporary) / "runtime") as store:
                artifact = store.put_artifact(b"Exercise artifact-local mapping wrappers.\n")
                store.submit(request("deep", [record("project", kind="project", provenance=provenance,
                                                    artifact_references=[artifact])]))
                captured = store.capture_snapshot(selection(), limits=limits())
            snapshot = DetachedSnapshot(captured.to_dict())
            first = plan_readable_snapshot(snapshot)
            rebuilt = ReadablePlan(first.snapshot_id, first.plan_id, first.generated_files,
                                   first.artifact_copies, first.directories, first.manifest_bytes)
            manifest = rebuilt.to_dict()
            verify_plan_links(rebuilt)
            second = plan_readable_snapshot(snapshot)
        self.assertEqual(first, rebuilt)
        self.assertEqual(first, second)
        self.assertEqual(first.manifest_bytes, second.manifest_bytes)
        self.assertEqual(len(first.artifact_copies), 1)
        expected = _canonical(provenance.to_dict())
        self.assertEqual(snapshot.records[0]["provenance_json"], expected)
        self.assertEqual(len(manifest["mappings"]), 1)
        self.assertEqual(len(manifest["artifacts"][0]["mappings"]), 1)
        for mapping in (*manifest["mappings"], *manifest["artifacts"][0]["mappings"]):
            self.assertEqual(_canonical(mapping["provenance"]), expected)

    def test_manifest_depth_above_69_is_rejected_at_construction(self):
        """A depth-70 artifact mapping fails the bounded parser through the public plan constructor."""
        with TemporaryDirectory(prefix="manifest-depth-") as temporary:
            with RecordStore.create(Path(temporary) / "runtime") as store:
                artifact = store.put_artifact(b"Mapping depth ceiling.\n")
                store.submit(request("project", [record("project", kind="project", artifact_references=[artifact])]))
                plan = plan_readable_snapshot(store.capture_snapshot(selection(), limits=limits()))
        document = plan.to_dict()
        value = 0
        for _ in range(63):
            value = [value]
        # Two provenance objects plus 63 lists and five manifest wrappers = 70.
        for mapping in (*document["mappings"], *document["artifacts"][0]["mappings"]):
            mapping["provenance"]["details"] = {"nested": value}
        document.pop("plan_id")
        identity = hashlib.sha256(_canonical(document).encode("ascii")).hexdigest()
        document["plan_id"] = identity
        data = _canonical(document).encode("ascii")
        generated = tuple(replace(file, data=data) if file.relative_path == "manifest.json" else file
                          for file in plan.generated_files)
        with self.assertRaisesRegex(ViewPlanError, "JSON nesting exceeds 69"):
            ReadablePlan(plan.snapshot_id, identity, generated, plan.artifact_copies, plan.directories, data)

    def test_dependent_notice_is_independent_of_record_order(self):
        """A project sorted before its disputed corpus retains raw routes without establishing the mapping."""
        with TemporaryDirectory(prefix="projection-order-") as temporary:
            with RecordStore.create(Path(temporary) / "runtime") as store:
                artifact = store.put_artifact(b"Synthetic original; no scientific evaluation.\n")
                original = source((artifact, artifact, artifact)).originals[0]
                captured = replace(uninspected(), originals=[original])
                selected = entry(selected=[original])
                selected = replace(selected, originals=[replace(selected.originals[0], path="disputed.tex")])
                store.submit(request("disputed", [
                    project_envelope("A-project", 1, setup(), CREATOR),
                    corpus_envelope("corpus", 1, inventory([selected]), CREATOR),
                    source_envelope("capture", 1, captured, CREATOR)]))
                snapshot = store.capture_snapshot(
                    SnapshotSelection(RootSelector("A-project", 1), ()), limits=limits())
            plan = plan_readable_snapshot(snapshot)
        records = {r["record_id"]: r for r in plan.to_dict()["records"]}
        self.assertEqual(next(iter(records)), "A-project")
        for identity in ("A-project", "corpus"):
            self.assertEqual(records[identity]["classification"]["category"], "locally_decoded")
            self.assertEqual(records[identity]["projection_limitation"]["category"],
                             "cross_record_projection_unavailable")
        self.assertIn("dependent corpus mapping", records["A-project"]["projection_limitation"]["detail"])
        self.assertEqual(len(plan.artifact_copies), 2)
        _, links = emitted_navigation(plan)
        self.assertIn(records["capture"]["page_path"], [p for p, _ in links[records["corpus"]["page_path"]]])
        for file in plan.generated_files:
            if file.role in ("index", "home"):
                provenance = file.data.decode().split("## Provenance\n\n", 1)[1].split("## Use", 1)[0]
                self.assertIn(plan.snapshot_id, provenance)

    def test_rehashed_inventory_types_roles_and_forged_modes_are_rejected(self):
        """Recomputed manifest IDs cannot disguise scalar coercions, false file roles or bypassed modes."""
        with TemporaryDirectory(prefix="plan-inventory-") as temporary:
            with RecordStore.create(Path(temporary) / "runtime") as store:
                artifact = store.put_artifact(b"x")
                store.submit(request("project", [record("project", kind="project", artifact_references=[artifact])]))
                plan = plan_readable_snapshot(store.capture_snapshot(selection(), limits=limits()))
        for field in ("size", "directory_mode", "descriptor_flag", "role"):
            document = plan.to_dict()
            generated = [file for file in plan.generated_files if file.relative_path != "manifest.json"]
            if field == "size":
                entry = next(item for item in document["files"] if item["role"] == "artifact_copy")
                entry["size"] = True  # Python equality would equate this with the recorded one byte.
            elif field == "directory_mode":
                document["directories"][0]["mode"] = float(document["directories"][0]["mode"])
            elif field == "descriptor_flag":
                document["descriptor"]["self_excluded"] = 1
            else:
                entry = next(item for item in document["files"] if item["role"] == "exact_envelope")
                entry["role"] = "index"
                generated = [replace(file, role="index") if file.relative_path == entry["path"] else file
                             for file in generated]
            document.pop("plan_id")
            identity = hashlib.sha256(_canonical(document).encode("ascii")).hexdigest()
            document["plan_id"] = identity
            data = _canonical(document).encode("ascii")
            generated.append(GeneratedFile("manifest.json", data, "manifest"))
            with self.subTest(field=field), self.assertRaises(ViewPlanError):
                ReadablePlan(plan.snapshot_id, identity, tuple(sorted(generated, key=lambda f: f.relative_path)),
                             plan.artifact_copies, plan.directories, data)
        for field in ("generated_files", "artifact_copies", "directories"):
            entries = list(getattr(plan, field))
            entries[0] = replace(entries[0])
            object.__setattr__(entries[0], "mode", 0o700)
            with self.subTest(field=field), self.assertRaises(ViewPlanError):
                replace(plan, **{field: tuple(entries)})
        verify_plan_links(plan)


class ViewPlanTests(unittest.TestCase):
    """Check generated metadata against synthetic committed values without granting admission or publication."""

    def setUp(self):
        """Create a private store and a coherent captured dossier reused within each independent case."""
        temporary = TemporaryDirectory(prefix="view-plan-tests-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.parent.chmod(0o700)
        self.store = RecordStore.create(self.parent / "runtime")
        self.addCleanup(self.store.close)
        self.chosen, self.payloads = populated(self.store, self.parent)
        self.snapshot = self.store.capture_snapshot(self.chosen, limits=limits())

    def plan(self):
        """Produce a fresh deterministic plan from the retained detached snapshot."""
        return plan_readable_snapshot(self.snapshot)

    def test_canonical_determinism_and_fresh_accessors(self):
        """Repeated projection and reconstructed dictionaries preserve every byte and both identities."""
        first, second = self.plan(), self.plan()
        self.assertEqual(first, second)
        document = self.snapshot.to_dict()
        reversed_keys = dict(reversed(list(document.items())))
        third = plan_readable_snapshot(DetachedSnapshot(reversed_keys))
        self.assertEqual(first, third)
        manifest = first.to_dict()
        manifest["records"][0]["classification"]["category"] = "forged"
        manifest["mappings"].clear()
        self.assertEqual(first, self.plan())
        canonical = first.to_dict()
        identity = canonical.pop("plan_id")
        self.assertEqual(identity, hashlib.sha256(_canonical(canonical).encode("ascii")).hexdigest())
        self.assertEqual(_canonical(first.to_dict()).encode("ascii"), first.manifest_bytes)
        self.assertNotIn("manifest.json", [f["path"] for f in first.to_dict()["files"]])
        self.assertIn("manifest.json", [f.relative_path for f in first.generated_files])

    def test_independent_hash_seed_processes(self):
        """Separate interpreters with different hash seeds derive identical complete plans from detached JSON."""
        path = self.parent / "snapshot.json"
        path.write_text(_canonical(self.snapshot.to_dict()), encoding="ascii")
        path.chmod(0o600)
        program = '''
import hashlib,json,sys
from research_pipeline.snapshot import DetachedSnapshot
from research_pipeline.view_plan import plan_readable_snapshot
with open(sys.argv[1], encoding="ascii") as stream:
    snapshot = DetachedSnapshot(json.load(stream))
plan = plan_readable_snapshot(snapshot)
print(plan.snapshot_id, plan.plan_id, hashlib.sha256(plan.manifest_bytes).hexdigest())
print([(f.relative_path, hashlib.sha256(f.data).hexdigest()) for f in plan.generated_files])
'''
        outputs = []
        for seed in ("1", "73491"):
            result = subprocess.run([sys.executable, "-B", "-c", program, str(path)], cwd=self.parent,
                env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONDONTWRITEBYTECODE": "1",
                     "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn(self.plan().plan_id, outputs[0])

    def test_all_generated_navigation_and_seven_fields(self):
        """Every emitted destination exists, every fragment is unique, every directory has seven-field README."""
        plan = self.plan()
        pages, graph = emitted_navigation(plan)
        files = {f.relative_path for f in (*plan.generated_files, *plan.artifact_copies)}
        for directory in plan.directories:
            path = (directory.relative_path + "/" if directory.relative_path else "") + "README.md"
            self.assertTrue(README_FIELDS <= set(pages[path]), path)
            for child in plan.directories:
                if child.relative_path and posixpath.dirname(child.relative_path) == directory.relative_path:
                    self.assertIn(child.relative_path + "/README.md", [target for target, _ in graph[path]])
            if directory.relative_path:
                parent = posixpath.dirname(directory.relative_path)
                parent_page = (parent + "/" if parent else "") + "README.md"
                self.assertIn(parent_page, [target for target, _ in graph[path]])
        for page, links in graph.items():
            slugs = [h.lower().replace(" ", "-").replace("/", "") for h in pages[page]]
            self.assertEqual(len(slugs), len(set(slugs)), page)
            for target, fragment in links:
                self.assertIn(target, files, (page, target))
                self.assertFalse(target.startswith("../"))
                if fragment:
                    self.assertIn(fragment, [h.lower().replace(" ", "-").replace("/", "") for h in pages[target]])
        self.assertTrue(any(fragment == "source-locations" for links in graph.values() for _, fragment in links))
        verify_plan_links(plan)

    def test_index_provenance_names_the_exact_snapshot(self):
        """Every useful generated index attributes its navigation to this exact detached generation."""
        plan = self.plan()
        indexes = [file for file in plan.generated_files if file.role == "index"]
        self.assertTrue(indexes)
        for file in indexes:
            provenance = file.data.decode().split("## Provenance\n\n", 1)[1].split("## Use", 1)[0]
            self.assertIn(plan.snapshot_id, provenance, file.relative_path)
            self.assertIn("expected_unverified", provenance)

    def test_home_claim_product_original_source_review_issue_routes(self):
        """The actual generated graph supplies home→claim→work product→authored artifact plus assessment/Source routes."""
        plan = self.plan()
        manifest = plan.to_dict()
        pages = {r["record_id"]: r["page_path"] for r in manifest["records"]}
        _, graph = emitted_navigation(plan)
        self.assertIn(pages["candidate"], [p for p, _ in graph["README.md"]])
        self.assertIn(pages["native-product"], [p for p, _ in graph[pages["candidate"]]])
        originals = [m["relative_path"] for m in manifest["mappings"] if m["logical_key"]["record_id"] == "native-product"]
        self.assertTrue(set(originals) <= {p for p, _ in graph[pages["native-product"]]})
        self.assertIn(pages["capture"], [p for p, _ in graph[pages["native-product"]]])
        for identity in ("review-a", "review-b", "claim-objection", "route", "alternative"):
            self.assertIn(pages[identity], [p for p, _ in graph[pages["candidate"]]])
        claim = next(f.data.decode() for f in plan.generated_files if f.relative_path == pages["candidate"])
        for heading in ("Assumptions", "Supporting justifications", "Contradictions and objections", "Reviews", "Open obligations"):
            self.assertIn("## " + heading, claim)
        self.assertIn('"provisional"', claim)
        self.assertIn("Hyperlink counts establish no support", claim)
        self.assertIn("Invalid support does not refute a claim", claim)

    def test_exact_originals_mappings_restrictions_and_expected_hashes(self):
        """Shared bytes receive distinct inert copies while mappings retain every exact source declaration."""
        plan = self.plan()
        manifest = plan.to_dict()
        copies = {c.relative_path: c for c in plan.artifact_copies}
        source_maps = [m for m in manifest["mappings"] if m["logical_key"]["record_id"] == "capture"]
        self.assertEqual(len(source_maps), 6)
        self.assertEqual({m["details"]["path"] for m in source_maps}, set(self.payloads))
        for mapping in source_maps:
            data = self.payloads[mapping["details"]["path"]]
            self.assertEqual(mapping["digest"], hashlib.sha256(data).hexdigest())
            self.assertEqual(copies[mapping["relative_path"]].size, len(data))
            self.assertEqual(mapping["details"]["original_mode"], 0o600)
            self.assertIn("external_processing", mapping["details"]["restrictions"])
            self.assertEqual(mapping["availability"], "expected_unverified")
        shared = [m for m in source_maps if m["details"]["path"] in ("copy.tex", "notes/seed.tex")]
        self.assertEqual(shared[0]["digest"], shared[1]["digest"])
        self.assertNotEqual(shared[0]["relative_path"], shared[1]["relative_path"])
        self.assertGreater(sum(c.size for c in plan.artifact_copies), sum(a["size"] for a in manifest["artifacts"]))
        self.assertTrue(all(entry["hash_kind"] == "expected" for entry in manifest["files"] if entry["role"] == "artifact_copy"))
        self.assertTrue(all(c.mode == 0o400 for c in plan.artifact_copies))
        self.assertTrue(all(d.mode == 0o500 for d in plan.directories))

    def test_literal_injection_properties_and_inert_names(self):
        """Hostile Markdown/HTML/control text and imported configuration names cannot become navigation or YAML."""
        plan = self.plan()
        manifest = plan.to_dict()
        for file in plan.generated_files:
            if not file.relative_path.endswith(".md"):
                continue
            text = file.data.decode()
            prose = "\n".join(line for line in text.splitlines() if not line.startswith("    "))
            self.assertNotIn("<script>", prose)
            self.assertNotIn("![image]", prose)
            self.assertNotIn("[[other]]", prose)
            self.assertNotIn("\u202e", text)
            self.assertNotIn("\x01", text)
            self.assertNotIn("https://example.invalid", prose)
            if text.startswith("---\n"):
                frontmatter = text.split("---\n", 2)[1]
                for line in frontmatter.splitlines():
                    name, scalar = line.split(": ", 1)
                    self.assertIsInstance(json.loads(scalar), str)
                    self.assertIn(name, {"record_id", "revision", "kind", "snapshot_id", "context_id", "context_revision", "branch_id", "branch_revision"})
        exact = [json.loads(r["envelope_json"])["content"] for r in manifest["records"] if r["record_id"] == "native-product"][0]
        self.assertEqual(exact["title"], HOSTILE)
        paths = [f.relative_path for f in (*plan.generated_files, *plan.artifact_copies)]
        self.assertFalse(any(".obsidian" in path or "settings.py" in path for path in paths))
        self.assertTrue(any(m["details"].get("original_path") == ".obsidian/settings.py" and m["relative_path"].endswith(".bin")
                            for m in manifest["mappings"]))
        self.assertTrue(any(m["details"].get("path") == "README.md" and "/originals/a-" in m["relative_path"] for m in manifest["mappings"]))

    def test_actual_branch_product_and_run_labels(self):
        """Only actual decoded product kinds create branch bundles and recorded run reports."""
        plan = self.plan()
        records = {r["record_id"]: r for r in plan.to_dict()["records"]}
        self.assertRegex(records["native-product"]["page_path"], r"^branches/r-[0-9a-f]{64}/notes/r-[0-9a-f]{64}/1/README.md$")
        self.assertRegex(records["run-report"]["page_path"], r"^reports/runs/r-[0-9a-f]{64}/r-[0-9a-f]{64}/1/README.md$")
        self.assertTrue(records["run"]["page_path"].startswith("navigation/records/run/"))
        generated = {f.relative_path: f.data.decode() for f in plan.generated_files if f.relative_path.endswith(".md")}
        self.assertIn("Recorded run report", generated[records["run-report"]["page_path"]])
        self.assertNotIn("Recorded run report", generated[records["run"]["page_path"]])
        branches = [f for f in plan.generated_files if f.relative_path.endswith("/branch.md")]
        self.assertEqual(len(branches), 1)
        self.assertIn("generic", branches[0].data.decode())
        self.assertIn("branch@1", branches[0].data.decode().replace("&#64;", "@"))
        prefixes = {d.relative_path.split("/")[0] for d in plan.directories}
        self.assertFalse(prefixes & {"runs", "tools", "drafts", "incoming", "state", "cache", "exports", "backups", ".obsidian"})

    def test_partial_and_cross_record_projection_limitations(self):
        """Locally valid opaque/disagreeing dossier targets remain linked without established typed mappings."""
        with RecordStore.create(self.parent / "partial") as store:
            # Generic submit deliberately retains a locally valid project with opaque corpus.
            store.submit(request("partial", [project_envelope("project", 1, setup(), CREATOR),
                                              record("corpus", kind="corpus_manifest")]))
            snapshot = store.capture_snapshot(selection(), limits=limits())
        plan = plan_readable_snapshot(snapshot)
        record_entry = next(r for r in plan.to_dict()["records"] if r["record_id"] == "project")
        self.assertEqual(record_entry["classification"]["category"], "locally_decoded")
        self.assertEqual(record_entry["projection_limitation"]["category"], "cross_record_projection_unavailable")
        home = next(f.data.decode() for f in plan.generated_files if f.relative_path == "README.md")
        self.assertIn("typed mapping projection unavailable", home)
        self.assertIn("recorded null", home)
        self.assertEqual(len(plan.to_dict()["records"]), 2)
        with RecordStore.create(self.parent / "disputed") as store:
            source_entry = next(r for r in self.snapshot.records if r["record_id"] == "capture")
            envelope = RecordEnvelope.from_dict(json.loads(source_entry["envelope_json"]))
            captured = decode_source(envelope)
            for data in self.payloads.values():
                store.put_artifact(data)
            selected = entry(selected=captured.originals[:1])
            # Keep both local codecs valid but disagree on the Source original mapping.
            selected = replace(selected, originals=[replace(selected.originals[0], path="different.tex")])
            corpus = inventory([selected])
            store.submit(request("disputed", [project_envelope("project", 1, setup(), CREATOR),
                corpus_envelope("corpus", 1, corpus, CREATOR), envelope]))
            disputed = plan_readable_snapshot(store.capture_snapshot(selection(), limits=limits()))
        target = next(r for r in disputed.to_dict()["records"] if r["record_id"] == "corpus")
        self.assertEqual(target["projection_limitation"]["category"], "cross_record_projection_unavailable")
        self.assertIn("mapping disagrees", target["projection_limitation"]["detail"])
        project = next(r for r in disputed.to_dict()["records"] if r["record_id"] == "project")
        self.assertEqual(project["classification"]["category"], "locally_decoded")
        self.assertIn("dependent corpus mapping projection unavailable", project["projection_limitation"]["detail"])
        project_page = next(f.data.decode() for f in disputed.generated_files if f.relative_path == project["page_path"])
        self.assertIn("disputed/unestablished mappings", project_page)
        home = next(f.data.decode() for f in disputed.generated_files if f.relative_path == "README.md")
        self.assertIn("initial&#95;corpus recorded target", home)
        self.assertIn("current&#95;corpus recorded target", home)

    def test_missing_categories_and_no_empty_runtime_hierarchy(self):
        """Minimal generic project generates useful indexes only and explicitly unavailable dossier categories."""
        with RecordStore.create(self.parent / "minimal") as store:
            simple_project(store)
            plan = plan_readable_snapshot(store.capture_snapshot(selection(), limits=limits()))
        home = next(f.data.decode() for f in plan.generated_files if f.relative_path == "README.md")
        self.assertIn("unavailable for opaque project", home)
        self.assertIn("Unavailable or not selected", home)
        self.assertNotIn("branches", {d.relative_path for d in plan.directories})
        self.assertFalse(plan.artifact_copies)
        self.assertFalse(any("originals" in d.relative_path for d in plan.directories))

    def test_exact_historical_revisions_and_case_distinct_long_ids(self):
        """Full hashes retain case-distinct and longest supported IDs; old revisions remain addressable."""
        identities = ("Case", "case", "A" * 128)
        self.store.submit(request("case-records", [record(identity, kind="decision") for identity in identities]))
        self.store.submit(request("case-next", [record("Case", 2, "decision")], {"Case": 1}))
        chosen = SnapshotSelection(self.chosen.project, (*self.chosen.roots, *(RootSelector(i, 1) for i in identities), RootSelector("Case", None)))
        plan = plan_readable_snapshot(self.store.capture_snapshot(chosen, limits=limits()))
        entries = [r for r in plan.to_dict()["records"] if r["record_id"] in identities]
        self.assertEqual(len(entries), 4)
        self.assertEqual(len({r["page_path"] for r in entries}), 4)
        for item in entries:
            token = "r-" + hashlib.sha256(item["record_id"].encode("ascii")).hexdigest()
            self.assertIn(token, item["page_path"])
            self.assertIn("/" + str(item["revision"]) + "/", item["page_path"])
        self.assertFalse(any("latest" in f.relative_path for f in plan.generated_files))

    def test_other_explicit_roots_remain_reachable_without_runtime_inference(self):
        """An explicitly selected generic event has a home link while its arbitrary success keys stay opaque."""
        self.store.submit(request("event-created", [record("event", kind="event", content={"success": True, "authorized": True})]))
        chosen = SnapshotSelection(self.chosen.project, (*self.chosen.roots, RootSelector("event", None)))
        plan = plan_readable_snapshot(self.store.capture_snapshot(chosen, limits=limits()))
        event = next(r for r in plan.to_dict()["records"] if r["record_id"] == "event")
        self.assertTrue(event["page_path"].startswith("navigation/records/event/"))
        _, graph = emitted_navigation(plan)
        self.assertIn(event["page_path"], [path for path, _ in graph["README.md"]])
        page = next(f.data.decode() for f in plan.generated_files if f.relative_path == event["page_path"])
        self.assertIn("Typed projection unavailable", page)
        self.assertNotIn("Recorded run report", page)

    def test_output_file_count_boundary(self):
        """Every generated README/envelope/manifest and every physical artifact copy consumes max_files."""
        plan = self.plan()
        count = len(plan.generated_files) + len(plan.artifact_copies)
        exact = self.store.capture_snapshot(self.chosen, limits=limits(max_files=count))
        self.assertEqual(len(plan_readable_snapshot(exact).to_dict()["files"]) + 1, count)
        short = self.store.capture_snapshot(self.chosen, limits=limits(max_files=count - 1))
        with self.assertRaises(SnapshotLimitError):
            plan_readable_snapshot(short)

    def test_physical_amplification_and_generated_byte_limits(self):
        """Unique capture bytes may fit while repeated copies and generated output exceed planning totals."""
        plan = self.plan()
        unique = sum(a["size"] for a in self.snapshot.artifacts)
        physical = sum(c.size for c in plan.artifact_copies)
        self.assertGreater(physical, unique)
        bounded = self.store.capture_snapshot(self.chosen, limits=limits(max_total_bytes=unique))
        with self.assertRaises(SnapshotLimitError):
            plan_readable_snapshot(bounded)
        largest_original = max(a["size"] for a in self.snapshot.artifacts)
        bounded = self.store.capture_snapshot(self.chosen, limits=limits(max_file_bytes=largest_original))
        with self.assertRaises(SnapshotLimitError):
            plan_readable_snapshot(bounded)
        # All content depends on effective limits; solve for the self-accounting boundary.
        total = sum(len(f.data) for f in plan.generated_files) + physical
        for _ in range(12):
            snapshot = self.store.capture_snapshot(self.chosen, limits=limits(max_total_bytes=total))
            try:
                candidate = plan_readable_snapshot(snapshot)
            except SnapshotLimitError:
                total += 1024
                continue
            needed = sum(len(f.data) for f in candidate.generated_files) + sum(c.size for c in candidate.artifact_copies)
            if total == needed:
                break
            total = needed
        self.assertEqual(total, sum(len(f.data) for f in candidate.generated_files) + sum(c.size for c in candidate.artifact_copies))
        with self.assertRaises(SnapshotLimitError):
            plan_readable_snapshot(self.store.capture_snapshot(self.chosen, limits=limits(max_total_bytes=total - 1)))

    def test_manifest_and_per_file_byte_boundary(self):
        """The largest generated file, including the self-excluded manifest, obeys its exact byte ceiling."""
        plan = self.plan()
        ceiling = max(len(f.data) for f in plan.generated_files)
        for _ in range(8):
            candidate = plan_readable_snapshot(self.store.capture_snapshot(self.chosen, limits=limits(max_file_bytes=ceiling)))
            needed = max(len(f.data) for f in candidate.generated_files)
            if needed == ceiling:
                break
            ceiling = needed
        else:
            self.fail("per-file accounting did not converge")
        self.assertEqual(max(len(f.data) for f in candidate.generated_files), ceiling)
        with self.assertRaises(SnapshotLimitError):
            plan_readable_snapshot(self.store.capture_snapshot(self.chosen, limits=limits(max_file_bytes=ceiling - 1)))

    def test_broken_links_fragments_and_unexpected_markdown_rejected(self):
        """Rehashed actual rendered defects are caught independently of manifest file hash checks."""
        plan = self.plan()
        home = next(f.data for f in plan.generated_files if f.relative_path == "README.md")
        for link in (b"[bad](missing.md)", b"[bad](../README.md)", b"[bad](/README.md)",
                     b"[bad](https://example.invalid)", b"[bad](README.md#absent)", b"[bad](brief)",
                     b"[bad](README.md#remaining-decisions#extra)", b"![image](README.md)",
                     b"[reference][id]", b"[[wikilink]]", b"<a href='README.md'>bad</a>",
                     b"## Remaining decisions"):
            damaged = forged_plan(plan, {"README.md": home + b"\n\n" + link + b"\n"})
            with self.subTest(link=link), self.assertRaises(ViewPlanError):
                verify_plan_links(damaged)

    def test_invalid_inventory_modes_aliases_and_generated_prefixes(self):
        """Public construction/consumption rejects forged immutable entries, portable collisions and unsafe paths."""
        plan = self.plan()
        for path in ("../README.md", "/absolute.md", "brief\\escape.md", "CON.txt", "README.MD", ".obsidian/settings.json",
                     "brief/README.md/child.md", "brief/" + "x" * 241 + "/README.md", "brief/é/README.md"):
            bad = object.__new__(ReadablePlan)
            for name in ("snapshot_id", "plan_id", "generated_files", "artifact_copies", "directories", "manifest_bytes"):
                object.__setattr__(bad, name, getattr(plan, name))
            object.__setattr__(bad, "generated_files", (*plan.generated_files, GeneratedFile(path, b"bad", "index")))
            with self.subTest(path=path), self.assertRaises(ViewPlanError):
                verify_plan_links(bad)
        with self.assertRaises(ViewPlanError):
            GeneratedFile("README.md", bytearray(b"mutable"), "index")
        with self.assertRaises(ViewPlanError):
            DirectoryEntry("brief", 0o700)
        with self.assertRaises(ViewPlanError):
            ArtifactCopy("bad", "a" * 64, True)
        with patch("research_pipeline.view_plan._token", return_value="r-" + "a" * 64), self.assertRaisesRegex(ViewPlanError, "collision"):
            self.plan()

    def test_planning_has_no_store_or_filesystem_access(self):
        """Planning with the store closed neither opens metadata nor reads/changes supplied original files."""
        before = {path: (self.parent / "inputs" / path).read_bytes() for path in self.payloads}
        self.store.close()
        with patch("sqlite3.connect", side_effect=AssertionError("no database")), \
             patch("builtins.open", side_effect=AssertionError("no filesystem")), \
             patch.object(Path, "open", side_effect=AssertionError("no path reads")):
            plan = self.plan()
            verify_plan_links(plan)
        self.assertEqual(before, {path: (self.parent / "inputs" / path).read_bytes() for path in self.payloads})
        self.assertTrue(plan.artifact_copies)
