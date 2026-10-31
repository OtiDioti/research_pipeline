"""Exact preservation, successor isolation and strict refresh input regression tests."""

from dataclasses import fields, replace
import json
import os
from pathlib import Path
from unittest.mock import patch

from research_pipeline.domain import DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError
from research_pipeline.vault import ViewLayoutError, ViewIntegrityError, ViewOperationalError, inspect_readable_view
from research_pipeline.view_plan import plan_readable_snapshot
from research_pipeline.view_refresh import refresh_readable_view
from tests.view_refresh_fixtures import RefreshFixture, refresh_limits
from tests.view_capture_fixtures import tree_state, SOURCE
from tests.snapshot_fixtures import limits, selection
from tests.test_assessment_store import metadata
from tests.test_store import record, request


class RefreshTests(RefreshFixture):
    """Observable package behavior keeps canonical metadata and the entire edited prior unchanged."""

    def test_same_plan_unchanged_and_successive_refresh(self):
        """Same-plan refresh publishes controls without divergent copies and can be refreshed again."""
        before, canonical = tree_state(self.view), metadata(self.runtime)
        objects = tree_state(self.runtime / "objects")
        result = self.refresh()
        self.assertTrue(result.same_plan)
        self.assertEqual(result.verification, "verified_at_refresh")
        self.assertFalse((Path(result.preservation_path) / "tree").exists())
        self.assertEqual(self.inspect(result).status, "published")
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(metadata(self.runtime), canonical)
        self.assertEqual(tree_state(self.runtime / "objects"), objects)
        next_result = refresh_readable_view(self.store, result.successor_path, self.parent / "again",
            expected_plan=self.plan, new_plan=self.plan, source_root=SOURCE, protected_roots=[], limits=refresh_limits())
        self.assertEqual(self.inspect(next_result).status, "published")
        self.assertEqual(inspect_readable_view(next_result.successor_path, limits=limits(), max_entries=4096).status, "verified")

    def test_edited_same_plan_and_new_revision_are_separate(self):
        """Generated YAML edits/additions remain inert proposed bytes and never feed successor rendering."""
        self.write("README.md", b"status: HUMAN DISPLAY EDIT\n")
        self.write("addition.md", b"[unsafe](../../outside)\n")
        before, canonical = tree_state(self.view), metadata(self.runtime)
        objects = tree_state(self.runtime / "objects")
        result = self.refresh()
        self.assertTrue(result.same_plan)
        self.assertEqual((Path(result.preservation_path) / "tree/README.md").read_bytes(), b"status: HUMAN DISPLAY EDIT\n")
        self.assertNotIn(b"HUMAN DISPLAY EDIT", (Path(result.successor_path) / "README.md").read_bytes())
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(metadata(self.runtime), canonical)
        self.assertEqual(tree_state(self.runtime / "objects"), objects)
        self.store.submit(request("advance", [record("project", 2, "project")], {"project": 1}))
        new = plan_readable_snapshot(self.store.capture_snapshot(selection(), limits=limits()))
        result2 = refresh_readable_view(self.store, self.view, self.parent / "new-revision", expected_plan=self.plan,
            new_plan=new, source_root=SOURCE, protected_roots=[], limits=refresh_limits())
        self.assertFalse(result2.same_plan)
        self.assertEqual(result2.successor_plan_id, new.plan_id)
        self.assertEqual(self.inspect(result2).status, "published")
        rows = json.loads((Path(result2.destination) / "refresh.json").read_bytes())["records"]
        self.assertEqual([(r["revision"], r["prior_root_ordinals"], r["successor_root_ordinals"]) for r in rows],
                         [(1, [0], []), (2, [], [0])])

    def test_renames_deletion_empty_directory_and_modes(self):
        """Every planned copy/empty directory survives exactly; missing paths remain metadata only."""
        self.rename("README.md", "renamed.yaml")
        self.write("renamed.yaml", b"rename plus edit\n")
        self.write("inert-script.py", b"raise RuntimeError('never execute')\n", 0o700)
        self.view.chmod(0o700)
        (self.view / "empty").mkdir(mode=0o700)
        (self.view / "manifest.json").unlink()
        before = tree_state(self.view)
        result = self.refresh()
        preservation = json.loads((Path(result.destination) / "preservation-plan.json").read_bytes())
        for row in preservation["files"]:
            target = Path(result.preservation_path) / row["preservation_path"]
            expected = self.plan.manifest_bytes if row["source_path"] is None else (self.view / row["source_path"]).read_bytes()
            self.assertEqual(target.read_bytes(), expected)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            if row["source_path"] is not None:
                self.assertNotEqual(target.stat().st_ino, (self.view / row["source_path"]).stat().st_ino)
        self.assertTrue((Path(result.preservation_path) / "tree/empty").is_dir())
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(self.inspect(result).status, "published")
        report = (Path(result.destination) / "README.md").read_text()
        self.assertIn("Rename-plus-edit", report)
        self.assertIn("checkout_work_product", report)
        self.assertIn("not prove which arbitrary authored", report)

    def test_detached_plans_do_not_read_live_metadata(self):
        """Canonical heads can advance while refresh consumes only supplied detached plans and objects."""
        self.store.submit(request("advance", [record("project", 2, "project")], {"project": 1}))
        with patch.object(self.store, "capture_snapshot", side_effect=AssertionError("live snapshot")), \
             patch.object(self.store, "get_revision", side_effect=AssertionError("record lookup")):
            result = self.refresh()
        self.assertEqual(result.successor_plan_id, self.plan.plan_id)

    def test_late_prior_mutation_keeps_mutators_bytes_and_retained_output(self):
        """The original observation is rechecked after the seam and cannot be silently replaced."""
        changed = []
        def mutate(point):
            """Simulate an editor at the final prepublication seam."""
            if point == "before_rename":
                self.write("README.md", b"late human edit\n")
                changed.append(tree_state(self.view))
        with patch("research_pipeline.view_refresh._fault", side_effect=mutate):
            with self.assertRaises(ViewIntegrityError) as raised:
                self.refresh()
        self.assertIn("attempt_path", str(raised.exception))
        self.assertEqual(tree_state(self.view), changed[0])
        self.assertFalse((self.parent / "successor").exists())
        self.assertEqual(len(list(self.parent.glob(".readable-refresh-package-*"))), 1)

    def test_strict_limits_and_occupied_destination(self):
        """All scalar budgets reject coercion/bypass mutations; occupied output remains intact."""
        for field in fields(refresh_limits()):
            if field.name in ("capture_limits", "successor_limits"):
                continue
            for value in (True, 1.5, None, -1, 2**63):
                with self.subTest(field=field.name, value=value), self.assertRaises(DomainValidationError):
                    replace(refresh_limits(), **{field.name: value})
            forged = refresh_limits()
            object.__setattr__(forged, field.name, True)
            with self.assertRaises(DomainValidationError):
                self.refresh(limits=forged)
        destination = self.parent / "successor"
        destination.write_bytes(b"competitor")
        destination.chmod(0o600)
        before = tree_state(self.parent)
        with self.assertRaises(ViewLayoutError):
            self.refresh()
        self.assertEqual(tree_state(self.parent), before)

    def test_outer_limits_fail_before_reservation(self):
        """Impossible known inventory/byte/descriptor allowances never reserve output."""
        for key in ("max_entries", "max_files", "max_directories", "max_depth", "max_file_bytes",
                    "max_total_bytes", "max_metadata_bytes", "max_diagnostics", "max_open_descriptors"):
            with self.subTest(limit=key), self.assertRaises(SnapshotLimitError):
                self.refresh(limits=refresh_limits(**{key: 1}))
            self.assertFalse(list(self.parent.glob(".readable-refresh-*")))

    def test_postrename_failure_is_uncertain_and_inspectable(self):
        """A lost acknowledgment leaves complete visible output and makes no historical fsync claim."""
        def fail(point):
            """Inject a real postrename I/O failure without cleanup."""
            if point == "after_rename":
                raise OSError(5, "injected EIO")
        with patch("research_pipeline.view_refresh._fault", side_effect=fail):
            with self.assertRaises(ViewOperationalError) as raised:
                self.refresh()
        self.assertIn("uncertain publication acknowledgment", str(raised.exception))
        self.assertIsNotNone(raised.exception.__cause__)
        from research_pipeline.view_refresh import inspect_readable_refresh
        attempt = next(self.parent.glob(".readable-refresh-attempt-*"))
        result = inspect_readable_refresh(attempt, self.parent / "successor", source_root=SOURCE,
                                         protected_roots=[], limits=refresh_limits())
        self.assertEqual(result.status, "published")
        self.assertEqual(result.publication_observation, "absent")
        self.assertEqual(result.historical_acknowledgment, "not_established")

    def test_authored_native_edits_and_changed_rich_selection(self):
        """Real captured native/source bytes and authored work remain proposed while closure changes are explicit."""
        self.populated_view()
        document = self.plan.to_dict()
        authored = next(m for m in document["mappings"] if m["logical_key"]["record_id"] == "native-product")
        native = next(m for m in document["mappings"] if m["logical_key"].get("original_path") == "native.bin")
        generated = next(r["page_path"] for r in document["records"] if r["record_id"] == "candidate")
        self.write(authored["relative_path"], b"edited authored Markdown [[old-target]]\n")
        self.write(native["relative_path"], b"\x00\xffedited scientific native\n")
        self.write(generated, b"---\nstatus: promoted-by-human-display-only\n---\n")
        chosen = plan_readable_snapshot(self.store.capture_snapshot(selection("native-product"), limits=limits()))
        before, canonical = tree_state(self.view), metadata(self.runtime)
        objects = tree_state(self.runtime / "objects")
        result = self.refresh(new_plan=chosen)
        for mapping in (authored, native):
            original = self.view / mapping["relative_path"]
            preserved = Path(result.preservation_path) / "tree" / mapping["relative_path"]
            self.assertEqual(preserved.read_bytes(), original.read_bytes())
        for file in chosen.generated_files:
            self.assertEqual((Path(result.successor_path) / file.relative_path).read_bytes(), file.data)
        association = json.loads((Path(result.destination) / "refresh.json").read_bytes())
        self.assertTrue(any(r["prior_root_ordinals"] and not r["successor_root_ordinals"] for r in association["records"]))
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(metadata(self.runtime), canonical)
        self.assertEqual(tree_state(self.runtime / "objects"), objects)
        self.assertEqual(self.inspect(result).status, "published")
