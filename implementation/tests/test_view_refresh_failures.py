"""Resource, mutation and layout failures retain original trees and explicit partial output."""

import errno
import json
import os
from pathlib import Path
from unittest.mock import patch

from research_pipeline.snapshot import RootSelector, SnapshotSelection, SnapshotLimitError
from research_pipeline.vault import ViewIntegrityError, ViewLayoutError, ViewOperationalError
from research_pipeline.view_plan import plan_readable_snapshot
from tests.view_refresh_fixtures import RefreshFixture, refresh_limits
from tests.view_capture_fixtures import tree_state
from tests.snapshot_fixtures import limits, selection
from tests.test_assessment_store import metadata
from tests.test_store import record, request


class RefreshFailureTests(RefreshFixture):
    """Meaningful independent failure cases do not convert partial work into refresh success."""

    def test_cross_project_fails_before_prior_reads(self):
        """Different requested/resolved project identities fail even with locally canonical plans."""
        self.store.submit(request("other", [record("other", kind="project")]))
        other = plan_readable_snapshot(self.store.capture_snapshot(
            SnapshotSelection(RootSelector("other", None), ()), limits=limits()))
        before = tree_state(self.parent)
        with patch("research_pipeline.view_capture._Observation.read", side_effect=AssertionError("prior read")):
            with self.assertRaises(ViewIntegrityError):
                self.refresh(new_plan=other)
        self.assertEqual(tree_state(self.parent), before)

    def test_changed_selection_and_historical_closure_mapping(self):
        """Exact union mappings retain omitted roots and historical dependencies without guessing a successor."""
        self.store.submit(request("note", [record("extra", kind="event")]))
        chosen = plan_readable_snapshot(self.store.capture_snapshot(selection("extra"), limits=limits()))
        result = self.refresh(new_plan=chosen)
        rows = json.loads((Path(result.destination) / "refresh.json").read_bytes())["records"]
        extra = next(r for r in rows if r["record_id"] == "extra")
        self.assertIsNone(extra["prior_page_path"])
        self.assertEqual(extra["successor_root_ordinals"], [1])
        self.assertEqual(self.inspect(result).status, "published")

    def test_io_resource_and_close_failures_keep_causes(self):
        """Actual read/write/sync/close failures are operational, never successful divergence."""
        before, canonical = tree_state(self.view), metadata(self.runtime)
        for operation, number in (("read", errno.EIO), ("write", errno.ENOSPC), ("fsync", errno.EIO),
                                  ("close", errno.EIO), ("open", errno.EMFILE)):
            actual = getattr(os, operation)
            fired = []
            def fail(*args, **kwargs):
                """Fail one OS operation, closing the real descriptor first when testing close errors."""
                if not fired:
                    fired.append(True)
                    if operation == "close":
                        actual(*args, **kwargs)
                    raise OSError(number, "injected " + operation)
                return actual(*args, **kwargs)
            with self.subTest(operation=operation), patch("os." + operation, side_effect=fail):
                with self.assertRaises(ViewOperationalError) as raised:
                    self.refresh()
            self.assertTrue(fired)
            self.assertIsNotNone(raised.exception.__cause__)
            self.assertEqual(tree_state(self.view), before)
            self.assertEqual(metadata(self.runtime), canonical)

    def test_output_and_evidence_tampering_before_gate(self):
        """Late prepared payload/evidence changes fail before the atomic publication boundary."""
        for kind in ("output", "evidence"):
            before = tree_state(self.view)
            def mutate(point):
                """Modify a prepared allocation after readiness, before the final verification gate."""
                if point == "before_rename":
                    prefix = ".readable-refresh-package-*" if kind == "output" else ".readable-refresh-attempt-*"
                    candidates = list(self.parent.glob(prefix))
                    target = max(candidates, key=lambda p: p.stat().st_mtime_ns) / ("README.md" if kind == "output" else "intent.json")
                    target.chmod(0o600)
                    target.write_bytes(b"tampered")
                    target.chmod(0o400)
            with self.subTest(kind=kind), patch("research_pipeline.view_refresh._fault", side_effect=mutate):
                with self.assertRaises(ViewIntegrityError):
                    self.refresh()
            self.assertFalse((self.parent / "successor").exists())
            self.assertEqual(tree_state(self.view), before)

    def test_equal_byte_inode_replacement_and_prior_root_rebinding(self):
        """The original observation detects equal-byte replacement and root renaming; mutator paths survive."""
        for kind in ("file", "root"):
            states = []
            def mutate(point):
                """Change the selected binding without pretending the refreshed observation can replace it."""
                if point != "before_rename":
                    return
                if kind == "file":
                    self.view.chmod(0o700)
                    target = self.view / "README.md"
                    data, mode = target.read_bytes(), target.stat().st_mode & 0o777
                    target.unlink()
                    target.write_bytes(data)
                    target.chmod(mode)
                else:
                    self.view.rename(self.parent / "human-moved-prior")
                states.append(tree_state(self.parent))
            with self.subTest(kind=kind), patch("research_pipeline.view_refresh._fault", side_effect=mutate):
                with self.assertRaises(ViewIntegrityError):
                    self.refresh()
            # Reservations were already made before the mutation; failure adds nothing afterward.
            self.assertEqual(tree_state(self.parent), states[0])

    def test_capture_time_mutation_and_source_binding_change(self):
        """Capture mutations and late canonical binding changes retain failure rather than recapturing."""
        fired = []
        def during_capture(point, path):
            """Change an already read prior file once, preserving the editor's final bytes."""
            if point == "file_read" and not fired:
                fired.append(True)
                self.write("README.md", b"mutator content\n")
        with patch("research_pipeline.view_capture._fault", side_effect=during_capture):
            with self.assertRaises(ViewIntegrityError):
                self.refresh()
        self.assertEqual((self.view / "README.md").read_bytes(), b"mutator content\n")
        object_path = self.runtime / "objects" / self.artifact.digest
        def source_change(point):
            """Replace one canonical binding after preparation; this deliberate mutation is test-owned."""
            if point == "before_rename":
                data = object_path.read_bytes()
                object_path.unlink()
                object_path.write_bytes(data)
                object_path.chmod(0o400)
        with patch("research_pipeline.view_refresh._fault", side_effect=source_change):
            with self.assertRaises(ViewIntegrityError):
                self.refresh()
        self.assertFalse((self.parent / "successor").exists())

    def test_safe_substitution_duplicate_owners_and_directory_rename(self):
        """Accepted planner associations are executed exactly for duplicate content and whole subtrees."""
        mapping = self.plan.to_dict()["mappings"][0]["relative_path"]
        folder = Path(mapping).parent
        self.view.chmod(0o700)
        self.view.joinpath(folder.parent).chmod(0o700)
        self.view.joinpath(folder).chmod(0o700)
        self.view.joinpath(folder).rename(self.view / "moved-bundle")
        self.write("duplicate.bin", self.store.read_artifact(self.artifact))
        self.view.chmod(0o700)
        (self.view / "manifest.json").unlink()
        (self.view / "manifest.json").mkdir(mode=0o700)
        self.write("manifest.json/addition", b"safe substituted bytes")
        before = tree_state(self.view)
        result = self.refresh()
        plan = json.loads((Path(result.destination) / "preservation-plan.json").read_bytes())
        self.assertTrue(any(g["basis"] == "exact_subtree" for g in plan["rename_groups"]))
        self.assertTrue(any("type_changed" in row["codes"] for row in plan["comparisons"]))
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(self.inspect(result).status, "published")

    def test_unsafe_prior_and_aliases_are_rejected_unchanged(self):
        """Unsafe prior entries and portable-alias additions never reach reservation or payload reads."""
        self.view.chmod(0o700)
        extra = self.view / "extra"
        for kind in ("symlink", "hardlink", "fifo", "shared", "alias"):
            if kind == "symlink":
                extra.symlink_to("missing")
            elif kind == "hardlink":
                os.link(self.view / "README.md", extra)
            elif kind == "fifo":
                os.mkfifo(extra, 0o600)
            elif kind == "alias":
                extra = self.view / "readme.md"
                extra.write_bytes(b"alias")
                extra.chmod(0o600)
            else:
                extra.write_bytes(b"shared")
                extra.chmod(0o644)
            before = tree_state(self.view)
            with self.subTest(kind=kind), self.assertRaises(ViewLayoutError):
                self.refresh()
            self.assertEqual(tree_state(self.view), before)
            extra.unlink()
        self.assertFalse(list(self.parent.glob(".readable-refresh-*")))

    def test_inspection_limits_cannot_be_enlarged_by_stored_budgets(self):
        """Each outer inventory/metadata/descriptor allowance remains independently enforced offline."""
        result = self.refresh()
        for key in ("max_entries", "max_files", "max_directories", "max_depth", "max_file_bytes",
                    "max_total_bytes", "max_metadata_bytes", "max_open_descriptors"):
            with self.subTest(limit=key), self.assertRaises(SnapshotLimitError):
                self.inspect(result, limits=refresh_limits(**{key: 1}))

    def test_exact_count_depth_boundaries_and_private_modes_under_umasks(self):
        """Complete physical counts and depths accept equality; output modes do not depend on permissive umasks."""
        initial = self.refresh(destination=self.parent / "measured")
        manifest = json.loads((Path(initial.destination) / "refresh.json").read_bytes())
        files = len(manifest["files"]) + 1 + 3
        directories = len(manifest["directories"]) + 1
        depth = max(len(r["path"].split("/")) for r in manifest["files"])
        exact = refresh_limits(max_files=files, max_directories=directories,
                               max_entries=files + directories - 1, max_depth=depth)
        for mask in (0, 0o022, 0o077):
            previous = os.umask(mask)
            try:
                result = self.refresh(destination=self.parent / ("umask-" + str(mask)), limits=exact)
            finally:
                os.umask(previous)
            self.assertEqual(self.inspect(result).status, "published")
            self.assertEqual(Path(result.destination).stat().st_mode & 0o777, 0o500)
            self.assertEqual(Path(result.preservation_path).stat().st_mode & 0o777, 0o700)
        for field, value in (("max_files", files - 1), ("max_directories", directories - 1),
                             ("max_entries", files + directories - 2), ("max_depth", depth - 1)):
            with self.subTest(field=field), self.assertRaises(SnapshotLimitError):
                self.refresh(limits=refresh_limits(**{field: value}))

    def test_owner_mask_fails_without_chmod_of_prior_or_destination(self):
        """Owner-bit masking fails closed when a newly reserved directory cannot be safely acquired."""
        before = tree_state(self.view)
        previous = os.umask(0o700)
        try:
            with self.assertRaises(ViewOperationalError):
                self.refresh()
        finally:
            os.umask(previous)
        self.assertEqual(tree_state(self.view), before)
        self.assertFalse((self.parent / "successor").exists())
        self.assertTrue(list(self.parent.glob(".readable-refresh-attempt-*")))

    def test_legitimate_canonical_staging_link_still_copies_independently(self):
        """Canonical object staging hardlinks are allowed while all refreshed outputs stay single-link."""
        object_path = self.runtime / "objects" / self.artifact.digest
        os.link(object_path, self.runtime / ".staging/legitimate")
        result = self.refresh()
        for entry in self.plan.artifact_copies:
            target = Path(result.successor_path) / entry.relative_path
            self.assertEqual(target.stat().st_nlink, 1)
            self.assertNotEqual(target.stat().st_ino, object_path.stat().st_ino)
        self.assertEqual(object_path.stat().st_nlink, 2)
