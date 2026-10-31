"""Exact detached comparison and complete planned-only preservation without canonical writes."""

import json
from unittest.mock import patch

from research_pipeline.snapshot import SnapshotLimitError, _canonical
from research_pipeline.vault import ViewIntegrityError
from research_pipeline.view_capture import _fields, _identified
from research_pipeline.view_preservation import plan_readable_preservation
from tests.test_assessment_store import metadata
from tests.test_store import record, request
from tests.view_capture_fixtures import CaptureFixture, capture_limits, tree_state


class PreservationTests(CaptureFixture):
    """Outcome tests for identity honesty, exact divergent copies and offline deterministic planning."""

    def planned(self):
        """Return one validated comparison document and its independently usable captured bytes."""
        captured = self.capture()
        return plan_readable_preservation(captured).to_dict(), captured

    def assert_copies(self, document, captured, paths):
        """Require each divergent ordinary path exactly once with its observed hash, size and bytes."""
        copies = [row for row in document["files"] if row["preservation_path"].startswith("tree/")]
        self.assertEqual([r["source_path"] for r in copies], sorted(paths))
        observed = {row["path"]: row for row in captured.to_dict()["files"]}
        for row in copies:
            self.assertEqual(row["preservation_path"], "tree/" + row["source_path"])
            self.assertEqual((row["sha256"], row["size"]),
                             (observed[row["source_path"]]["sha256"], len(captured.file_bytes(row["source_path"]))))
        self.assertEqual(document["status"], "planned_only")

    def test_unchanged_offline_deterministic_and_detached(self):
        """Unchanged trees retain every byte and two controls, with no divergence or live reads."""
        before, canonical = tree_state(self.view), metadata(self.runtime)
        captured = self.capture()
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(metadata(self.runtime), canonical)
        self.store.close()
        with patch("os.open", side_effect=AssertionError("filesystem read")), \
             patch("os.stat", side_effect=AssertionError("filesystem stat")), \
             patch("os.scandir", side_effect=AssertionError("filesystem enumeration")):
            first = plan_readable_preservation(captured)
            second = plan_readable_preservation(captured)
            self.assertEqual(first.to_dict(), second.to_dict())
            result = first.to_dict()
            self.assertFalse(any(row["codes"] for row in result["comparisons"]))
            self.assertEqual(result["missing"], [])
            self.assertEqual(result["target_diagnostics"], [])
            self.assert_copies(result, captured, [])
            self.assertEqual([r["preservation_path"] for r in result["files"]],
                             ["controls/expected-manifest.json", "controls/observed-manifest.bin"])
            for item in self.plan.generated_files:
                self.assertEqual(captured.file_bytes(item.relative_path), item.data)
            result["files"][0]["size"] = 0
            self.assertNotEqual(first.to_dict()["files"][0]["size"], 0)

    def test_head_advance_cannot_change_independent_base(self):
        """A later canonical revision does not silently select a newer expected plan during capture."""
        self.store.submit(request("advance", [record("project", 2, kind="project", content={"later": True})],
                                  {"project": 1}))
        result, captured = self.planned()
        self.assertEqual(captured.expected_plan_id, self.plan.plan_id)
        self.assertEqual(captured.expected_manifest_bytes, self.plan.manifest_bytes)
        self.assertFalse(any(row["codes"] for row in result["comparisons"]))
        self.assertEqual(self.store.head("project"), 2)

    def test_forged_ancestor_depth_rejected_before_prefix_expansion(self):
        """Rehashed deep paths cannot bypass descriptor bounds via a small retained ancestor array."""
        captured = self.capture()
        original = captured.to_dict()
        allowance = captured._limits.max_open_descriptors
        inventory_descriptors = len(original["files"]) + len(original["directories"]) + 1
        self.assertLessEqual(len(original["ancestors"]) + inventory_descriptors, allowance)
        cases = (("/" + "/".join(["a"] * (allowance + 1)), SnapshotLimitError),
                 (original["prior_view"] + "/extra", ViewIntegrityError),
                 ("/", ViewIntegrityError))
        def guard_fields(value, names, label):
            """Fail if ancestor rows are traversed before lexical depth has been validated."""
            if label == "ancestor":
                raise AssertionError("ancestor row processed before depth preflight")
            return _fields(value, names, label)
        for prior, error in cases:
            with self.subTest(depth=prior.count("/"), error=error.__name__):
                document = dict(original, prior_view=prior)
                document["capture_id"] = _identified(document, "capture_id")
                state = _canonical(document)
                self.assertLessEqual(len(state) + len(document["expected_manifest"]),
                                     captured._limits.max_metadata_bytes)
                required = 0 if prior == "/" else prior.count("/")
                if error is SnapshotLimitError:
                    self.assertGreater(required + inventory_descriptors, allowance)
                else:
                    self.assertLessEqual(required + inventory_descriptors, allowance)
                    self.assertNotEqual(required, len(document["ancestors"]))
                object.__setattr__(captured, "_state", state)
                with patch("research_pipeline.view_capture.Path", side_effect=AssertionError("prefix expansion")), \
                     patch("research_pipeline.view_capture._fields", side_effect=guard_fields):
                    with self.assertRaises(error):
                        captured.to_dict()
                    with self.assertRaises(error):
                        plan_readable_preservation(captured)

    def test_exact_descriptor_boundary_retains_complete_offline_ancestor_chain(self):
        """A valid exact-budget capture retains root-to-parent order and can be planned without I/O."""
        document = self.capture().to_dict()
        boundary = len(document["ancestors"]) + len(document["files"]) + len(document["directories"]) + 1
        captured = self.capture(limits=capture_limits(max_open_descriptors=boundary))
        expected = [str(path) for path in reversed(self.view.parents)]
        self.store.close()
        with patch("os.open", side_effect=AssertionError("filesystem read")), \
             patch("os.stat", side_effect=AssertionError("filesystem stat")), \
             patch("os.scandir", side_effect=AssertionError("filesystem enumeration")):
            self.assertEqual([row["path"] for row in captured.to_dict()["ancestors"]], expected)
            planned = plan_readable_preservation(captured).to_dict()
            self.assertEqual(planned["capture_id"], captured.capture_id)
            self.assertEqual(planned["status"], "planned_only")
            self.assertFalse(any(row["codes"] for row in planned["comparisons"]))

    def test_generated_status_and_native_binary_edits_are_proposed(self):
        """Same-path generated/binary edits keep old mappings and separate byte identities exactly."""
        self.populated_view()
        mappings = self.plan.to_dict()["mappings"]
        artifact = next(m for m in mappings if m["logical_key"]["record_id"] == "native-product")
        page = next(r["page_path"] for r in self.plan.to_dict()["records"] if r["record_id"] == "candidate")
        self.write(page, b"scientific_status: accepted\n[[active]]\n")
        self.write(artifact["relative_path"], b"\x00\xffproposed native edit")
        before, canonical = tree_state(self.view), metadata(self.runtime)
        result, captured = self.planned()
        self.assert_copies(result, captured, [page, artifact["relative_path"]])
        rows = {r["expected_path"]: r for r in result["comparisons"]}
        for path in (page, artifact["relative_path"]):
            row = rows[path]
            self.assertIn("content_changed", row["codes"])
            self.assertEqual(row["association_basis"], "exact_path")
            self.assertNotEqual(row["expected_sha256"], row["observed_sha256"])
        retained = json.loads(captured.expected_manifest_bytes)
        self.assertEqual(retained["mappings"], mappings)
        self.assertEqual(retained["records"], self.plan.to_dict()["records"])
        self.assertIn("not authenticated", result["explanation"])
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(metadata(self.runtime), canonical)

    def test_mode_only_file_and_directory(self):
        """Owner execute is inert divergence; planned output permissions remain private and nonexecuting."""
        (self.view / "README.md").chmod(0o500)
        result, captured = self.planned()
        row = next(r for r in result["comparisons"] if r["expected_path"] == "README.md")
        self.assertEqual(row["codes"], ["mode_changed"])
        self.assertEqual(row["expected_sha256"], row["observed_sha256"])
        self.assert_copies(result, captured, ["README.md"])
        self.view.chmod(0o700)
        result, _ = self.planned()
        directory = next(r for r in result["directories"] if r["source_path"] == "")
        self.assertEqual((directory["observed_mode"], directory["mode"]), (0o700, 0o700))

    def test_unique_file_rename_retains_bytes_and_missing_target(self):
        """Unique unchanged generated bytes establish a rename but never a canonical deletion."""
        self.rename("README.md", "renamed.md")
        result, captured = self.planned()
        row = next(r for r in result["comparisons"] if r["expected_path"] == "README.md")
        self.assertEqual((row["observed_path"], row["association_basis"]), ("renamed.md", "exact_bytes"))
        self.assertIn("renamed", row["codes"])
        self.assert_copies(result, captured, ["renamed.md"])
        self.assertIn("README.md", [r["expected_path"] for r in result["missing"]])
        diagnostic = next(r for r in result["target_diagnostics"] if r["expected_path"] == "README.md")
        self.assertEqual(diagnostic["preservation_path"], "tree/renamed.md")

    def test_complete_directory_rename_disambiguates_duplicate_contents(self):
        """A unique complete prior structure can associate contained duplicate originals by suffix."""
        self.rename("brief", "moved")
        result, captured = self.planned()
        original = [f.relative_path for f in (*self.plan.generated_files, *self.plan.artifact_copies)
                    if f.relative_path.startswith("brief/")]
        self.assert_copies(result, captured, ["moved" + p[len("brief"):] for p in original])
        rows = [r for r in result["comparisons"] if r["expected_path"] and r["expected_path"].startswith("brief/")]
        self.assertTrue(all(r["association_basis"] == "exact_subtree" for r in rows))
        groups = [g for g in result["rename_groups"] if g["basis"] == "exact_subtree"]
        self.assertEqual(len(groups), 1)
        self.assertFalse(groups[0]["ambiguous"])

    def test_directory_rename_with_edit_does_not_claim_complete_subtree(self):
        """Edited moved structure retains unresolved bytes and independently exact unchanged matches."""
        page = next(r["page_path"] for r in self.plan.to_dict()["records"])
        self.rename("brief", "moved")
        edited = "moved" + page[len("brief"):]
        self.write(edited, b"renamed and edited human work")
        result, captured = self.planned()
        self.assertFalse(any(g["basis"] == "exact_subtree" and g["expected_paths"] == ["brief"]
                             for g in result["rename_groups"]))
        added = next(r for r in result["comparisons"] if r["observed_path"] == edited)
        self.assertEqual(added["association_basis"], "unresolved")
        self.assertIn("added_unresolved", added["codes"])
        self.assertEqual(captured.file_bytes(edited), b"renamed and edited human work")
        self.assertIn("Rename-plus-edit", result["explanation"])

    def test_duplicate_owners_and_extra_copies_remain_ambiguous(self):
        """Unchanged canonical occurrences participate in ambiguity, with all original owners retained."""
        first, second = [a.relative_path for a in self.plan.artifact_copies]
        self.rename(first, "copy.bin")
        result, captured = self.planned()
        group = next(g for g in result["rename_groups"] if first in g["expected_paths"])
        self.assertEqual(group["expected_paths"], sorted([first, second]))
        self.assertEqual(group["observed_paths"], sorted([second, "copy.bin"]))
        self.assertTrue(group["ambiguous"])
        row = next(r for r in result["comparisons"] if r["expected_path"] == first)
        self.assertIsNone(row["observed_path"])
        self.assertIn("ambiguous", row["codes"])
        self.assertEqual(captured.file_bytes("copy.bin"), self.store.read_artifact(self.artifact))
        self.assert_copies(result, captured, [second, "copy.bin"])

    def test_unique_owner_with_extra_duplicate_is_not_a_rename(self):
        """Competing observations prevent guessing between identical added files."""
        home = (self.view / "README.md").read_bytes()
        self.rename("README.md", "first.md")
        self.write("second.md", home, 0o400)
        result, captured = self.planned()
        row = next(r for r in result["comparisons"] if r["expected_path"] == "README.md")
        self.assertIsNone(row["observed_path"])
        self.assertIn("ambiguous", row["codes"])
        self.assert_copies(result, captured, ["first.md", "second.md"])

    def test_additions_deletions_and_empty_inert_content(self):
        """Extra Unicode/configuration trees, empty bytes and empty directories all remain represented."""
        self.view.chmod(0o700)
        (self.view / ".obsidian").mkdir(mode=0o700)
        (self.view / ".obsidian/empty").mkdir(mode=0o700)
        self.write(".obsidian/α.json", b"")
        (self.view / "README.md").unlink()
        result, captured = self.planned()
        self.assert_copies(result, captured, [".obsidian/α.json"])
        self.assertEqual(captured.file_bytes(".obsidian/α.json"), b"")
        self.assertIn("tree/.obsidian/empty", [r["preservation_path"] for r in result["directories"]])
        self.assertFalse(any(r["source_path"] == "README.md" for r in result["files"]))
        self.assertIn("README.md", [r["expected_path"] for r in result["missing"]])

    def test_safe_file_to_directory_and_directory_to_file_substitutions(self):
        """Stable safe type changes preserve actual bytes and identify every blocked descendant."""
        self.view.chmod(0o700)
        (self.view / "README.md").unlink()
        (self.view / "README.md").mkdir(mode=0o700)
        self.write("README.md/note", b"substituted subtree")
        self.rename("brief", "saved-brief")
        self.write("brief", b"directory became a file")
        result, captured = self.planned()
        rows = {r["expected_path"]: r for r in result["comparisons"] if r["expected_path"] is not None}
        self.assertIn("type_changed", rows["README.md"]["codes"])
        self.assertIn("type_changed", rows["brief"]["codes"])
        for row in result["missing"]:
            if row["expected_path"].startswith("brief/"):
                self.assertEqual(row["blocked_ancestor"], "brief")
        planned = {r["source_path"] for r in result["files"]}
        self.assertIn("README.md/note", planned)
        self.assertIn("brief", planned)
        self.assertEqual(captured.file_bytes("brief"), b"directory became a file")

    def test_swapped_contents_remain_exact_path_proposals(self):
        """Byte matches at occupied paths never silently transfer historical ownership."""
        page = next(r["page_path"] for r in self.plan.to_dict()["records"])
        first, second = (self.view / "README.md").read_bytes(), (self.view / page).read_bytes()
        self.write("README.md", second)
        self.write(page, first)
        result, captured = self.planned()
        self.assert_copies(result, captured, ["README.md", page])
        rows = [r for r in result["comparisons"] if r["expected_path"] in ("README.md", page)]
        self.assertTrue(all(r["association_basis"] == "exact_path" for r in rows))
        self.assertTrue(all("content_changed" in r["codes"] for r in rows))
        self.assertTrue(all("ambiguous" in r["codes"] for r in rows))

    def test_manifest_missing_changed_corrupt_and_type_changed(self):
        """Observed controls never establish inventory, even when absent or not JSON."""
        for value in (b"garbage\xff", b'{"plan_id":"invented","files":[]}', None, "directory"):
            with self.subTest(value=value):
                manifest = self.view / "manifest.json"
                self.view.chmod(0o700)
                if manifest.exists():
                    manifest.unlink()
                if value == "directory":
                    manifest.mkdir(mode=0o700)
                    self.write("manifest.json/preserved", b"safe control subtree")
                elif value is not None:
                    self.write("manifest.json", value)
                result, captured = self.planned()
                self.assertTrue(all(row["reasons"] == sorted(row["reasons"]) for row in result["files"]))
                self.assertEqual(captured.expected_manifest_bytes, self.plan.manifest_bytes)
                self.assertEqual({r["expected_path"] for r in result["comparisons"] if r["expected_path"] is not None},
                                 {f.relative_path for f in (*self.plan.generated_files, *self.plan.artifact_copies, *self.plan.directories)})
                controls = [r for r in result["files"] if r["preservation_path"] == "controls/observed-manifest.bin"]
                self.assertEqual(bool(controls), type(value) is bytes)
                if type(value) is bytes:
                    self.assertEqual(captured.file_bytes("manifest.json"), value)

    def test_planning_metadata_and_diagnostic_limits_fail_without_partial_result(self):
        """Every full row consumes diagnostics; aggregate metadata includes both controls and explanation."""
        captured = self.capture()
        result = plan_readable_preservation(captured).to_dict()
        count = sum(len(result[key]) for key in ("comparisons", "rename_groups", "missing", "target_diagnostics"))
        for allowance, success in ((count - 1, False), (count, True), (count + 1, True)):
            bounded = self.capture(limits=capture_limits(max_diagnostics=allowance))
            if success:
                self.assertEqual(plan_readable_preservation(bounded).to_dict()["status"], "planned_only")
            else:
                with self.assertRaises(SnapshotLimitError):
                    plan_readable_preservation(bounded)
        minimum = len(captured._state) + len(captured.expected_manifest_bytes)
        bounded = self.capture(limits=capture_limits(max_metadata_bytes=minimum + 100))
        with self.assertRaises(SnapshotLimitError):
            plan_readable_preservation(bounded)

    def test_bypassed_capture_and_plan_fields_are_not_consumable(self):
        """Fresh accessors reject forged hashes, payloads, schema fields and inconsistent references."""
        captured = self.capture()
        original = captured._state
        for change in ("version", "unknown", "size", "entries"):
            document = json.loads(original)
            if change == "version":
                document["version"] = True
            elif change == "unknown":
                document["unknown"] = 1
            elif change == "size":
                document["files"][0]["size"] = True
            else:
                document["directories"][0]["entries"].append("invented")
            document["capture_id"] = _identified(document, "capture_id")
            object.__setattr__(captured, "_state", _canonical(document))
            with self.assertRaises((ViewIntegrityError, ValueError)):
                plan_readable_preservation(captured)
        object.__setattr__(captured, "_state", original)
        payloads = captured._payloads
        object.__setattr__(captured, "_payloads", ((payloads[0][0], b"forged"), *payloads[1:]))
        with self.assertRaises(ViewIntegrityError):
            captured.file_bytes(payloads[0][0])
        object.__setattr__(captured, "_payloads", payloads)
        plan = plan_readable_preservation(captured)
        object.__setattr__(plan, "_state", plan._state.replace('"planned_only"', '"published"'))
        with self.assertRaises(ViewIntegrityError):
            plan.to_dict()

    def test_duplicate_associations_are_compact_and_budgeted(self):
        """Many identical observations use one complete group, without expanding owner/copy pairs."""
        expected = [a.relative_path for a in self.plan.artifact_copies]
        data = self.store.read_artifact(self.artifact)
        for number in range(20):
            self.write(f"duplicate-{number:02d}", data, 0o400)
        result, captured = self.planned()
        groups = [g for g in result["rename_groups"] if g["expected_paths"] == expected]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["observed_paths"]), 22)
        self.assertTrue(groups[0]["ambiguous"])
        count = sum(len(result[key]) for key in ("comparisons", "rename_groups", "missing", "target_diagnostics"))
        bounded = self.capture(limits=capture_limits(max_diagnostics=count - 1))
        with self.assertRaises(SnapshotLimitError):
            plan_readable_preservation(bounded)
        self.assertEqual(len([r for r in result["files"] if r["preservation_path"].startswith("tree/")]), 22)

    def test_exact_aggregate_preservation_metadata_boundary(self):
        """The capture, independent manifest, plan JSON and readable explanation share one exact ceiling."""
        captured = self.capture()
        original = captured.to_dict()
        planned = plan_readable_preservation(captured).to_dict()
        plan_size = len(_canonical(planned)) + len(planned["explanation"].encode("utf-8"))
        boundary = len(captured._state) + len(captured.expected_manifest_bytes) + plan_size
        for _ in range(3):
            original["limits"]["max_metadata_bytes"] = boundary
            boundary = len(_canonical(original)) + len(original["expected_manifest"]) + plan_size
        for delta in (-1, 0, 1):
            with self.subTest(delta=delta):
                bounded = self.capture(limits=capture_limits(max_metadata_bytes=boundary + delta))
                if delta < 0:
                    with self.assertRaises(SnapshotLimitError):
                        plan_readable_preservation(bounded)
                else:
                    self.assertEqual(plan_readable_preservation(bounded).to_dict()["status"], "planned_only")

    def test_strict_json_and_complete_retained_schema(self):
        """Unknown fields, duplicate JSON keys, nonfinite numbers and forged signatures never load implicitly."""
        captured = self.capture()
        original = captured._state
        for state in (original + " ", '{"version":1,"version":1}', '{"number":NaN}', '{"version":1.0}'):
            object.__setattr__(captured, "_state", state)
            with self.subTest(state=state[:40]), self.assertRaises(ViewIntegrityError):
                captured.to_dict()
        for field, value in (("mode", True), ("device", -1), ("nlink", 2), ("inode", 2**63)):
            document = json.loads(original)
            document["files"][0]["signature"][field] = value
            document["capture_id"] = _identified(document, "capture_id")
            object.__setattr__(captured, "_state", _canonical(document))
            with self.subTest(field=field), self.assertRaises((ViewIntegrityError, ValueError)):
                captured.to_dict()
        object.__setattr__(captured, "_state", original)
        detached = captured.to_dict()
        detached["limits"]["plan_limits"]["max_files"] = 1
        self.assertNotEqual(captured.to_dict()["limits"]["plan_limits"]["max_files"], 1)
