"""Independent outer preservation/control and nested capture admission boundaries."""

from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import patch

from research_pipeline.snapshot import SnapshotLimitError, _canonical
from research_pipeline.view_capture import _Observation, _validated_metadata
from research_pipeline.vault import ViewIntegrityError
from tests.view_refresh_fixtures import RefreshFixture, refresh_limits
from tests.view_capture_fixtures import tree_state
from tests.test_assessment_store import metadata


class RefreshBudgetRepairTests(RefreshFixture):
    """Measure actual physical/control copies independently and reject before prohibited reads."""

    def test_hash_only_divergence_is_admitted_before_installing_payload(self):
        """Same-size/mode edits require comparison reads but cannot install an unbudgeted copy."""
        measured = self.refresh(destination=self.parent / "measured")
        manifest = json.loads((Path(measured.destination) / "refresh.json").read_bytes())
        maximum = len(manifest["files"]) + 4
        relative = self.plan.artifact_copies[0].relative_path
        original_bytes = (self.view / relative).read_bytes()
        self.write(relative, b"!" + original_bytes[1:], mode=0o400)
        before = tree_state(self.view), metadata(self.runtime)
        original, observed = _Observation.read, []
        def read(observation, fd, info, path, **kwargs):
            """Retain the observation object only to verify rejected bytes were never installed."""
            result = original(observation, fd, info, path, **kwargs)
            if path == relative:
                observed.append(observation)
            return result
        with patch.object(_Observation, "read", read), self.assertRaises(SnapshotLimitError):
            self.refresh(limits=refresh_limits(max_files=maximum))
        self.assertEqual(len(observed), 1)
        self.assertNotIn(relative, dict(observed[0].payloads))
        self.assertFalse(any(row["path"] == relative for row in observed[0].document["files"]))
        self.assertEqual((tree_state(self.view), metadata(self.runtime)), before)

    def test_opaque_control_metadata_admission_precedes_capture_and_inspection_reads(self):
        """Opaque evidence consumes aggregate control allowance even when parsing needs no bytes."""
        self.write("manifest.json", b"\xff" * 2_000_000)
        before = tree_state(self.view), metadata(self.runtime)
        original = _Observation.read
        def read(observation, fd, info, path, **kwargs):
            """Refuse a test failure if an already oversized control reaches the read boundary."""
            self.assertNotEqual(path, "manifest.json")
            return original(observation, fd, info, path, **kwargs)
        with patch.object(_Observation, "read", read), self.assertRaises(SnapshotLimitError):
            self.refresh(limits=refresh_limits(max_metadata_bytes=1_000_000))
        self.assertFalse(list(self.parent.glob(".readable-refresh-*")))
        result = self.refresh()
        from research_pipeline.view_refresh_inspection import _inspect_open
        def open_control(stack, parent, name, info, path):
            """Confirm opaque observed evidence is charged before opening, despite retain=False."""
            self.assertNotEqual(path, "package/preservation/controls/observed-manifest.bin")
            return _inspect_open(stack, parent, name, info, path)
        with patch("research_pipeline.view_refresh_inspection._inspect_open", open_control):
            with self.assertRaises(SnapshotLimitError):
                self.inspect(result, limits=refresh_limits(max_metadata_bytes=1_000_000))
        self.assertEqual((tree_state(self.view), metadata(self.runtime)), before)

    def test_added_oversize_file_is_refused_before_its_first_read(self):
        """Outer file admission precedes nested-permitted reads and every output/object reservation."""
        self.write("oversized.bin", b"x" * 1_000_001)
        before = tree_state(self.view), metadata(self.runtime)
        original, reads = _Observation.read, []
        def read(observation, fd, info, path, **kwargs):
            """Record real capture read boundaries for the specifically oversized new payload."""
            if path == "oversized.bin":
                reads.append(path)
            return original(observation, fd, info, path, **kwargs)
        with patch.object(_Observation, "read", read), patch(
                "research_pipeline.view_refresh._create", side_effect=AssertionError("output reservation")), patch(
                "research_pipeline.view_refresh._prepare_generation", side_effect=AssertionError("object reads")):
            with self.assertRaises(SnapshotLimitError):
                self.refresh(limits=refresh_limits(max_file_bytes=1_000_000))
        self.assertEqual(reads, [])
        self.assertEqual((tree_state(self.view), metadata(self.runtime)), before)
        self.assertFalse(list(self.parent.glob(".readable-refresh-*")))
        exact = self.refresh(limits=refresh_limits(max_file_bytes=1_000_001))
        self.assertEqual(self.inspect(exact).status, "published")
        self.assertEqual((tree_state(self.view), metadata(self.runtime)), before)

    def test_duplicate_associations_and_rename_fit_exact_physical_counts(self):
        """Final ambiguity copies count separately while deterministic rename choices remain unchanged."""
        self.write("extra-copy.bin", b"duplicate synthetic original\n")
        self.rename("README.md", "renamed.md")
        measured = self.refresh(destination=self.parent / "measure")
        manifest = json.loads((Path(measured.destination) / "refresh.json").read_bytes())
        preservation = json.loads((Path(measured.destination) / "preservation-plan.json").read_bytes())
        self.assertTrue(any(row["ambiguous"] for row in preservation["rename_groups"]))
        self.assertTrue(any("renamed" in row["codes"] for row in preservation["comparisons"]))
        files, directories = len(manifest["files"]) + 4, len(manifest["directories"]) + 1
        total = sum(row["size"] for row in manifest["files"])
        total += (Path(measured.destination) / "refresh.json").stat().st_size
        for path in Path(measured.attempt_path).iterdir():
            value = json.loads(path.read_bytes())
            value["package"] = [2**64 - 1] * 2
            if path.name == "intent.json":
                value["parent"] = [2**64 - 1] * 2
            total += len(_canonical(value))
        exact = refresh_limits(max_files=files, max_directories=directories,
            max_entries=files + directories - 1, max_total_bytes=total)
        before = tree_state(self.view), metadata(self.runtime)
        result = self.refresh(destination=self.parent / "atlimit", limits=exact)
        self.assertEqual(self.inspect(result).status, "published")
        for field in ("max_files", "max_directories", "max_entries", "max_total_bytes"):
            with self.subTest(field=field), self.assertRaises(SnapshotLimitError):
                self.refresh(destination=self.parent / "belowit", limits=replace(exact, **{field: getattr(exact, field) - 1}))
        self.assertEqual((tree_state(self.view), metadata(self.runtime)), before)

    def test_incremental_cumulative_files_bytes_and_prefixed_depth(self):
        """Each entry fits capture while cumulative output and prefixed depth reject before its read."""
        self.write("a-extra.bin", b"a" * 100_000)
        self.write("z-extra.bin", b"z" * 100_000)
        baseline = self.refresh(destination=self.parent / "measured")
        root = Path(baseline.destination)
        manifest = json.loads((root / "refresh.json").read_bytes())
        all_files = len(manifest["files"]) + 4
        limits_cases = [refresh_limits(max_files=all_files - 1)]
        # Fixed admission has known successor/control bytes, then two divergent
        # files. Report/capture bytes are not a precondition for early admission.
        known = (sum(len(e.data) for e in self.plan.generated_files)
                 + sum(e.size for e in self.plan.artifact_copies) + 2 * len(self.plan.manifest_bytes))
        limits_cases.append(refresh_limits(max_total_bytes=known + 150_000))
        before = tree_state(self.view), metadata(self.runtime)
        original = _Observation.read
        for index, chosen in enumerate(limits_cases):
            reads = []
            def read(observation, fd, info, path, **kwargs):
                """Observe the second divergent file's initial read without replacing real I/O."""
                if path == "z-extra.bin":
                    reads.append(path)
                return original(observation, fd, info, path, **kwargs)
            with self.subTest(index=index), patch.object(_Observation, "read", read):
                with self.assertRaises(SnapshotLimitError):
                    self.refresh(destination=self.parent / ("refused-" + str(index)), limits=chosen)
                self.assertEqual(reads, [])
            self.assertEqual((tree_state(self.view), metadata(self.runtime)), before)
        # The published successor's deepest path fits; the additional preservation
        # prefix puts this safe prior directory beyond the outer ceiling.
        depth = max(len(row["path"].split("/")) for row in manifest["files"])
        directory = self.view
        directory.chmod(0o700)
        for index in range(depth - 1):
            directory = directory / ("deep" + str(index))
            directory.mkdir(mode=0o700)
        (directory / "payload").write_bytes(b"bounded")
        (directory / "payload").chmod(0o600)
        before = tree_state(self.view), metadata(self.runtime)
        with self.assertRaises(SnapshotLimitError):
            self.refresh(limits=refresh_limits(max_depth=depth))
        self.assertEqual((tree_state(self.view), metadata(self.runtime)), before)

    def control_total(self, result, *, placeholders=False):
        """Count actual serialized controls and control copies, independently of production builders."""
        root, attempt = Path(result.destination), Path(result.attempt_path)
        names = ["capture.json", "preservation-plan.json", "refresh.json", "README.md", "generation/manifest.json",
                 "preservation/controls/expected-manifest.json", "preservation/controls/observed-manifest.bin"]
        total = sum((root / name).stat().st_size for name in names if (root / name).is_file())
        for path in attempt.iterdir():
            value = json.loads(path.read_bytes())
            if placeholders:
                value["package"] = [2**64 - 1] * 2
                if path.name == "intent.json":
                    value["parent"] = [2**64 - 1] * 2
            total += len(_canonical(value))
        return total

    def test_actual_opaque_manifest_metadata_exact_refresh_and_inspection_boundaries(self):
        """An enlarged opaque observed control counts once at actual size, including attempt evidence."""
        opaque = b"\xff\x00opaque human evidence\n" * 50_000
        self.write("manifest.json", opaque)
        self.write("authored.json", b"a" * 500_000)
        prior, canonical = tree_state(self.view), metadata(self.runtime)
        measured = self.refresh(destination=self.parent / "measure")
        self.assertEqual((Path(measured.preservation_path) / "controls/observed-manifest.bin").read_bytes(), opaque)
        total = self.control_total(measured, placeholders=True)
        exact = self.refresh(destination=self.parent / "atlimit", limits=refresh_limits(max_metadata_bytes=total))
        self.assertEqual(self.inspect(exact).status, "published")
        with self.assertRaises(SnapshotLimitError):
            self.refresh(destination=self.parent / "belowit", limits=refresh_limits(max_metadata_bytes=total - 1))
        self.assertFalse((self.parent / "belowit").exists())
        inspection_total = self.control_total(exact)
        self.assertEqual(self.inspect(exact, limits=refresh_limits(max_metadata_bytes=inspection_total)).status, "published")
        with self.assertRaises(SnapshotLimitError):
            self.inspect(exact, limits=refresh_limits(max_metadata_bytes=inspection_total - 1))
        observed = Path(exact.preservation_path) / "controls/observed-manifest.bin"
        with observed.open("r+b") as stream:
            stream.write(b"!")
        damaged = tree_state(Path(exact.destination))
        inspected = self.inspect(exact, limits=refresh_limits(max_metadata_bytes=inspection_total))
        self.assertEqual(inspected.status, "inconsistent")
        self.assertIsNone(inspected.successor_path)
        self.assertEqual(tree_state(Path(exact.destination)), damaged)
        self.assertEqual((tree_state(self.view), metadata(self.runtime)), (prior, canonical))

    def test_missing_and_directory_manifest_have_no_phantom_control_copy(self):
        """Absent and directory-substituted controls add no fictitious observed-manifest metadata."""
        self.view.chmod(0o700)
        (self.view / "manifest.json").unlink()
        for kind in ("missing", "directory"):
            if kind == "directory":
                (self.view / "manifest.json").mkdir(mode=0o700)
            with self.subTest(kind=kind):
                measured = self.refresh(destination=self.parent / (kind + "-measure"))
                total = self.control_total(measured, placeholders=True)
                result = self.refresh(destination=self.parent / (kind + "-atlimit"),
                                      limits=refresh_limits(max_metadata_bytes=total))
                self.assertFalse((Path(result.preservation_path) / "controls/observed-manifest.bin").exists())
                self.assertEqual(self.inspect(result, limits=refresh_limits(
                    max_metadata_bytes=self.control_total(result))).status, "published")
                with self.assertRaises(SnapshotLimitError):
                    self.refresh(destination=self.parent / (kind + "-belowit"),
                                 limits=refresh_limits(max_metadata_bytes=total - 1))

    def test_independent_capture_metadata_limits_before_read_and_after_parse(self):
        """Nested text and aggregate allowances raise budget errors, while corruption stays inconsistent."""
        result = self.refresh()
        root = Path(result.destination)
        capture = (root / "capture.json").read_bytes()
        limits = refresh_limits()
        chosen = replace(limits, capture_limits=replace(limits.capture_limits, max_metadata_bytes=len(capture) - 1))
        from research_pipeline.view_refresh_inspection import _inspect_open
        opened = []
        def open_control(stack, parent, name, info, path):
            """Record attempted capture opens; insufficient stat allowance must reject before this boundary."""
            if path == "package/capture.json":
                opened.append(path)
            return _inspect_open(stack, parent, name, info, path)
        with patch("research_pipeline.view_refresh_inspection._inspect_open", open_control):
            with self.assertRaises(SnapshotLimitError):
                self.inspect(result, limits=chosen)
        self.assertEqual(opened, [])
        for maximum in (len(capture), len(capture) + len(self.plan.manifest_bytes) - 1):
            with self.subTest(maximum=maximum), self.assertRaises(SnapshotLimitError):
                self.inspect(result, limits=replace(limits, capture_limits=replace(
                    limits.capture_limits, max_metadata_bytes=maximum)))
        preservation = (root / "preservation-plan.json").read_bytes()
        full = len(capture) + len(self.plan.manifest_bytes) + len(preservation)
        full += len(json.loads(preservation)["explanation"].encode("utf-8"))
        exact = replace(limits, capture_limits=replace(limits.capture_limits, max_metadata_bytes=full))
        self.assertEqual(self.inspect(result, limits=exact).status, "published")
        control = root / "capture.json"
        control.chmod(0o600)
        control.write_bytes(b"{}")
        control.chmod(0o400)
        self.assertEqual(self.inspect(result, limits=exact).status, "inconsistent")
        with self.assertRaises(SnapshotLimitError):
            _validated_metadata("x" * 101, replace(limits.capture_limits, max_metadata_bytes=100))
        with self.assertRaises(ViewIntegrityError):
            _validated_metadata(b"x", limits.capture_limits)

    def test_public_refresh_signature_and_complete_private_path_inventory(self):
        """Public refresh retains its signature and passes complete physical inventory without a new ceiling."""
        import inspect
        from research_pipeline import view_refresh
        self.assertEqual(tuple(inspect.signature(view_refresh.refresh_readable_view).parameters),
            ("source", "prior_view", "destination", "expected_plan", "new_plan", "source_root", "protected_roots", "limits"))
        self.write("manifest.json", b"opaque authored control")
        self.write("native.txt", b"native draft")
        (self.view / "empty").mkdir(mode=0o700)
        original, observed = view_refresh._absolute_paths, []
        def admit(files, directories, destination, package_path, attempt_path, maximum):
            """Observe the real final inventory at the shared gate, then retain its normal admission behavior."""
            observed.append((files, directories, maximum))
            self.assertFalse(destination.exists())
            self.assertFalse(package_path.exists())
            self.assertFalse(attempt_path.exists())
            return original(files, directories, destination, package_path, attempt_path, maximum)
        with patch.object(view_refresh, "_absolute_paths", admit):
            result = self.refresh()
        self.assertEqual(self.inspect(result).status, "published")
        self.assertEqual(len(observed), 1)
        files, directories, maximum = observed[0]
        self.assertIsNone(maximum)
        paths = {row["path"] for row in files}
        self.assertTrue({"capture.json", "preservation-plan.json", "README.md", "refresh.json",
            "preservation/controls/expected-manifest.json", "preservation/controls/observed-manifest.bin",
            "preservation/tree/native.txt", "attempt/intent.json", "attempt/ready.json",
            "attempt/published.json"} <= paths)
        self.assertTrue({"generation/" + entry.relative_path for entry in self.plan.generated_files} <= paths)
        self.assertTrue({"generation/" + entry.relative_path for entry in self.plan.artifact_copies} <= paths)
        self.assertTrue({"", "attempt", "preservation/controls", "preservation/tree/empty", "generation"}
                        <= {row["path"] for row in directories})
        # Every actual inventory row is checked under each possible physical root.
        for row in (*files, *directories):
            relative = row["path"]
            for target in (("attempt",) if relative == "attempt" or relative.startswith("attempt/")
                           else ("destination", "package")):
                with self.subTest(path=relative, target=target):
                    suffix = relative.partition("/")[2] if target == "attempt" else relative
                    # Include multibyte scalar values; character counts would miss one-over.
                    root_size = 4096 - (len(suffix.encode("utf-8")) + 1 if suffix else 0)
                    root = Path("/" + "é" * ((root_size - 1) // 2) + "x" * ((root_size - 1) % 2))
                    roots = dict(destination=Path("/d"), package=Path("/p"), attempt=Path("/a"))
                    roots[target] = root
                    original([row] if row in files else [], [row] if row in directories else [],
                             roots["destination"], roots["package"], roots["attempt"], 4096)
                    roots[target] = Path(str(root) + "x")
                    with self.assertRaises(SnapshotLimitError):
                        original([row] if row in files else [], [row] if row in directories else [],
                                 roots["destination"], roots["package"], roots["attempt"], 4096)
        # No synthetic package/attempt path may consume the package-root allowance.
        original([dict(path="attempt/published.json")], [dict(path="attempt")],
                 Path("/" + "d" * 4095), Path("/" + "p" * 4095), Path("/a"), 4096)
        with self.assertRaises(SnapshotLimitError):
            original([], [], Path("/\ud800"), Path("/p"), Path("/a"), 4096)
