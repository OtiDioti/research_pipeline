"""Real read-only filesystem safety, finite bounds and coordinated capture consistency tests."""

from dataclasses import fields, replace
import errno
import os
from pathlib import Path
import selectors
import socket
import stat
import subprocess
import sys
from unittest.mock import patch

from research_pipeline.domain import DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError, _canonical
from research_pipeline.vault import ViewLayoutError, ViewIntegrityError, ViewOperationalError, inspect_readable_view
from research_pipeline.view_capture import capture_readable_view
from research_pipeline.view_plan import ViewPlanError
from tests.snapshot_fixtures import limits
from tests.test_assessment_store import metadata
from tests.test_vault import child_environment
from tests.test_view_plan import forged_plan
from tests.view_capture_fixtures import CaptureFixture, SOURCE, capture_limits, tree_state


class CaptureTests(CaptureFixture):
    """Capture all safe work without touching modes, paths, bytes or canonical storage."""

    def test_exact_public_types_and_frozen_limit_revalidation(self):
        """Mandatory signed-64-bit values reject all coercions at construction and consumption."""
        valid = capture_limits()
        for field in fields(valid):
            if field.name == "plan_limits":
                continue
            for bad in (True, 1.0, None, "1", -1, 2**63):
                with self.subTest(field=field.name, bad=bad), self.assertRaises(DomainValidationError):
                    replace(valid, **{field.name: bad})
        for name in ("max_file_bytes", "max_total_bytes"):
            with self.assertRaises(SnapshotLimitError):
                self.capture(limits=replace(valid, **{name: 0}))
        for bad in ({}, None, self.plan.plan_id):
            with self.assertRaises(DomainValidationError):
                self.capture(expected_plan=bad)
        object.__setattr__(valid.plan_limits, "max_files", True)
        with self.assertRaises(DomainValidationError):
            self.capture(limits=valid)

    def test_independent_preflight_before_reconstruction_or_observation(self):
        """Supplied plan budgets cannot authorize work and over-limit metadata never reaches reconstruction."""
        with patch("research_pipeline.view_capture.readable_plan_from_manifest", side_effect=AssertionError("render")), \
             patch("os.open", side_effect=AssertionError("observe")):
            for options in (dict(max_files=1), dict(max_directories=1), dict(max_entries=1),
                            dict(max_metadata_bytes=1), dict(max_file_bytes=1), dict(max_total_bytes=1)):
                with self.subTest(options=options), self.assertRaises(SnapshotLimitError):
                    self.capture(limits=capture_limits(**options))
        with self.assertRaises(SnapshotLimitError):
            self.capture(limits=capture_limits(plan_limits=replace(limits(), max_files=1)))
        home = next(f.data for f in self.plan.generated_files if f.relative_path == "README.md")
        with self.assertRaises(ViewPlanError):
            self.capture(expected_plan=forged_plan(self.plan, {"README.md": home + b"\nNoncanonical.\n"}))

    def test_expected_and_observed_counts_bytes_depth_boundaries(self):
        """Each complete physical inventory includes manifest/root and independently consumes every budget."""
        captured = self.capture().to_dict()
        files, directories = captured["files"], captured["directories"]
        exact = dict(max_files=len(files), max_directories=len(directories),
            max_entries=len(files) + len(directories) - 1,
            max_file_bytes=max(row["size"] for row in files), max_total_bytes=sum(row["size"] for row in files),
            max_depth=max(len(row["path"].split("/")) for row in files),
            max_open_descriptors=len(captured["ancestors"]) + len(files) + len(directories) + 1)
        for name, boundary in exact.items():
            for delta in (-1, 0, 1):
                with self.subTest(name=name, delta=delta):
                    budgets = capture_limits(**{name: boundary + delta})
                    if delta < 0:
                        with self.assertRaises(SnapshotLimitError):
                            self.capture(limits=budgets)
                    else:
                        self.assertEqual(len(self.capture(limits=budgets).to_dict()["files"]), len(files))
        self.write("extra", b"x" * (exact["max_file_bytes"] + 1))
        for name in ("max_files", "max_entries", "max_file_bytes", "max_total_bytes"):
            with self.subTest(extra=name), self.assertRaises(SnapshotLimitError):
                self.capture(limits=capture_limits(**{name: exact[name]}))

    def test_unexpected_nested_depth_and_directory_limits(self):
        """Safe unexpected trees consume full traversal allowances before deeper descendants are opened."""
        self.view.chmod(0o700)
        parent = self.view
        for number in range(10):
            parent /= str(number)
            parent.mkdir(mode=0o700)
        with self.assertRaises(SnapshotLimitError):
            self.capture(limits=capture_limits(max_depth=9))
        with self.assertRaises(SnapshotLimitError):
            self.capture(limits=capture_limits(max_directories=len(self.plan.directories)))
        self.assertIn("/".join(str(n) for n in range(10)), [d["path"] for d in self.capture().to_dict()["directories"]])

    def test_exact_aggregate_capture_metadata_boundary(self):
        """Escaped canonical manifest text and complete capture JSON both count at the exact boundary."""
        captured = self.capture()
        document = captured.to_dict()
        boundary = len(captured._state) + len(captured.expected_manifest_bytes)
        for _ in range(3):
            document["limits"]["max_metadata_bytes"] = boundary
            boundary = len(_canonical(document)) + len(document["expected_manifest"])
        for delta in (-1, 0, 1):
            with self.subTest(delta=delta):
                if delta < 0:
                    with self.assertRaises(SnapshotLimitError):
                        self.capture(limits=capture_limits(max_metadata_bytes=boundary + delta))
                else:
                    self.assertEqual(self.capture(limits=capture_limits(max_metadata_bytes=boundary + delta)).expected_plan_id,
                                     self.plan.plan_id)

    def test_utf8_component_and_relative_path_ceilings(self):
        """Unicode ceilings use actual UTF-8 bytes; safe exact-limit names remain unchanged."""
        self.write("é" * 120, b"exact 240 UTF-8 bytes")
        self.assertEqual(self.capture().file_bytes("é" * 120), b"exact 240 UTF-8 bytes")
        self.write("é" * 121, b"over")
        with self.assertRaises(ViewLayoutError):
            self.capture()
        (self.view / ("é" * 121)).unlink()
        parent, pieces = self.view, []
        for index in range(4):
            name = str(index) + "a" * 239
            pieces.append(name)
            parent /= name
            parent.mkdir(mode=0o700)
        name = "b" * 60  # four 240-byte directories, four separators, 60-byte leaf = 1024
        relative = "/".join([*pieces, name])
        self.write(relative, b"exact relative ceiling")
        self.assertEqual(self.capture().file_bytes(relative), b"exact relative ceiling")
        self.write(relative + "c", b"over")
        with self.assertRaises(ViewLayoutError):
            self.capture()

    def test_portable_aliases_include_expected_missing_paths(self):
        """Case/NFKC-only moves conflict even when the original canonical spelling is absent."""
        for destination in ("readme.md", "ＲＥＡＤＭＥ.md"):
            self.rename("README.md", destination)
            with self.subTest(destination=destination), self.assertRaises(ViewLayoutError):
                self.capture()
            self.rename(destination, "README.md")
        self.write("NUL.txt", b"reserved")
        with self.assertRaises(ViewLayoutError):
            self.capture()

    def test_unsafe_original_names_and_non_scalar_bytes(self):
        """Original traversal-like, reserved, non-scalar and control spellings are never normalized into opens."""
        self.view.chmod(0o700)
        for name in ("trailing.", "back\\slash", "a:b", "bad\nname", "com1", "\udcff"):
            path = self.view / name
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            with self.subTest(name=repr(name)), self.assertRaises(ViewLayoutError):
                self.capture()
            path.unlink()
        with self.assertRaises(ViewLayoutError):
            capture_readable_view(self.view / ".." / "reading", expected_plan=self.plan,
                source_root=SOURCE, protected_roots=[], limits=capture_limits())

    def test_exclusion_overlap_in_both_directions_and_input_bounds(self):
        """Explicit boundaries are checked component-wise and caller root lists are bounded first."""
        for root in (self.view, self.view.parent, self.view / "child"):
            with self.subTest(root=root), self.assertRaises(ViewLayoutError):
                self.capture(protected_roots=[root])
            with self.assertRaises(ViewLayoutError):
                self.capture(source_root=root)
        with self.assertRaises(DomainValidationError):
            self.capture(protected_roots=iter([self.runtime]))
        with self.assertRaises(SnapshotLimitError):
            self.capture(protected_roots=[self.runtime] * 4096)
        with self.assertRaises(SnapshotLimitError):
            self.capture(protected_roots=["x" * 50_000_001])

    def test_symlink_ancestors_children_dangling_and_hardlinks(self):
        """No-follow traversal refuses both ancestor aliases and unsafe ordinary/control leaves."""
        self.view.chmod(0o700)
        alias = self.parent / "alias"
        alias.symlink_to(self.view, target_is_directory=True)
        with self.assertRaises(ViewLayoutError):
            capture_readable_view(alias, expected_plan=self.plan, source_root=SOURCE,
                                  protected_roots=[], limits=capture_limits())
        for target in ("README.md", "absent"):
            link = self.view / "unsafe"
            link.symlink_to(target)
            with self.assertRaises(ViewLayoutError):
                self.capture()
            link.unlink()
        os.link(self.view / "README.md", self.view / "hardlink")
        before = tree_state(self.view)
        with self.assertRaises(ViewLayoutError):
            self.capture()
        self.assertEqual(tree_state(self.view), before)

    def test_fifo_socket_and_private_mode_contract(self):
        """Special entries and shared/special/inaccessible modes fail before bytes are consumed."""
        self.view.chmod(0o700)
        special = self.view / "special"
        os.mkfifo(special, 0o600)
        with self.assertRaises(ViewLayoutError):
            self.capture()
        special.unlink()
        with socket.socket(socket.AF_UNIX) as server:
            previous = Path.cwd()
            try:
                os.chdir(self.view)
                server.bind("special")
            finally:
                os.chdir(previous)
            with self.assertRaises(ViewLayoutError):
                self.capture()
        special.unlink()
        self.assertEqual(self.capture().expected_plan_id, self.plan.plan_id)

    def test_private_file_and_directory_modes(self):
        """Shared, special and inaccessible entries fail; safe owner modes remain inert captured data."""
        home = self.view / "README.md"
        for mode in (0o000, 0o200, 0o644, 0o444, 0o4600):
            home.chmod(mode)
            with self.subTest(mode=oct(mode)), self.assertRaises(ViewLayoutError):
                self.capture()
            home.chmod(0o400)
        for mode in (0o400, 0o600, 0o700, 0o500):
            home.chmod(mode)
            self.assertEqual(self.capture().file_bytes("README.md"), home.read_bytes())
        self.view.chmod(0o750)
        with self.assertRaises(ViewLayoutError):
            self.capture()

    def test_stat_open_resource_and_permission_errors_are_operational(self):
        """EIO, ENFILE, EMFILE and access failures retain causes and never become divergence."""
        self.write("README.md", b"divergent human work")
        before = tree_state(self.view)
        for number in (errno.EIO, errno.ENFILE, errno.EMFILE, errno.EACCES, errno.EPERM):
            with self.subTest(number=number), patch("os.open", side_effect=OSError(number, "injected")), \
                 self.assertRaises(ViewOperationalError) as caught:
                self.capture()
            self.assertEqual(caught.exception.__cause__.errno, number)
        self.assertEqual(tree_state(self.view), before)

    def test_fixed_ancestor_markers_without_unbounded_listing(self):
        """Recognizable runtime/attempt ancestors fail via fixed stat checks, never os.listdir."""
        with patch("os.listdir", side_effect=AssertionError("unbounded listing")):
            self.capture()
        marker = self.parent / "ready.json"
        marker.write_bytes(b"opaque")
        marker.chmod(0o600)
        with self.assertRaises(ViewLayoutError):
            self.capture()

    def test_read_only_guards_and_existing_inspector_remains_nonrecursive(self):
        """Capture preserves all canonical/prior state and does not weaken the inspector's opaque extras."""
        self.view.chmod(0o700)
        (self.view / "extra").mkdir(mode=0o700)
        self.write("extra/authored", b"work")
        (self.view / "extra/unsafe").symlink_to("authored")
        result = inspect_readable_view(self.view, limits=limits(), max_entries=4096,
                                       expected_plan_id=self.plan.plan_id)
        self.assertTrue(any(d.relative_path == "extra" for d in result.differences))
        self.assertFalse(any(d.relative_path == "extra/unsafe" for d in result.differences))
        (self.view / "extra/unsafe").unlink()
        before, canonical, objects = tree_state(self.view), metadata(self.runtime), tree_state(self.runtime / "objects")
        with patch("os.chmod", side_effect=AssertionError("chmod")), \
             patch("os.fchmod", side_effect=AssertionError("fchmod")), \
             patch("os.write", side_effect=AssertionError("write")), \
             patch("os.fsync", side_effect=AssertionError("fsync")), \
             patch.object(self.store, "head", side_effect=AssertionError("canonical access")), \
             patch.object(self.store, "submit", side_effect=AssertionError("submit")):
            self.assertEqual(self.capture().file_bytes("extra/authored"), b"work")
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(metadata(self.runtime), canonical)
        self.assertEqual(tree_state(self.runtime / "objects"), objects)

    def test_mutations_at_private_seams_keep_mutators_final_work(self):
        """Earlier edits, equal-byte replacements, membership and mode changes cannot escape final gates."""
        cases = ("edit", "replace", "membership", "mode", "nested", "root")
        for case in cases:
            with self.subTest(case=case):
                self.view = self.parent / ("reading-" + case)
                self.publish()
                self.view.chmod(0o700)
                (self.view / "README.md").chmod(0o600)
                changed = False
                final = None
                def mutate(boundary, path):
                    """Apply one real mutation after bytes have been captured, then preserve its final state."""
                    nonlocal changed, final
                    if changed or boundary != "before_final_gate":
                        return
                    changed = True
                    home = self.view / "README.md"
                    if case == "edit":
                        home.write_bytes(b"latest human work")
                    elif case == "replace":
                        data = home.read_bytes()
                        home.unlink()
                        home.write_bytes(data)
                        home.chmod(0o600)
                    elif case == "membership":
                        (self.view / "new-directory").mkdir(mode=0o700)
                    elif case == "mode":
                        home.chmod(0o400)
                    elif case == "nested":
                        (self.view / "brief").rename(self.view / "renamed-brief")
                    else:
                        self.view.rename(self.parent / "moved-root")
                        self.view.mkdir(mode=0o700)
                    final = tree_state(self.parent)
                with patch("research_pipeline.view_capture._fault", side_effect=mutate), self.assertRaises(ViewIntegrityError):
                    self.capture()
                self.assertTrue(changed)
                self.assertEqual(tree_state(self.parent), final)

    def test_external_ancestor_membership_is_not_view_mutation(self):
        """Trusted ancestors may gain unrelated siblings without invalidating held view bindings."""
        def mutate(boundary, path):
            """Change only an external ancestor's membership at the final observation seam."""
            if boundary == "before_final_gate":
                (self.parent / "unrelated").mkdir(mode=0o700)
        with patch("research_pipeline.view_capture._fault", side_effect=mutate):
            self.assertEqual(self.capture().expected_plan_id, self.plan.plan_id)

    def test_external_ancestor_membership_during_open_is_not_view_mutation(self):
        """A sibling created between ancestor stat/open leaves the complete prior observation valid."""
        before, canonical = tree_state(self.view), metadata(self.runtime)
        objects = tree_state(self.runtime / "objects")
        sibling = self.parent / "unrelated-during-open"
        calls = 0
        def mutate(boundary, path):
            """Create one real unrelated directory after the parent's initial no-follow stat."""
            nonlocal calls
            if boundary == "before_open" and path == str(self.parent):
                calls += 1
                sibling.mkdir(mode=0o700)
        with patch("research_pipeline.view_capture._fault", side_effect=mutate):
            captured = self.capture()
        self.assertEqual(calls, 1)
        self.assertEqual(captured.expected_plan_id, self.plan.plan_id)
        self.assertEqual(captured.expected_manifest_bytes, self.plan.manifest_bytes)
        self.assertEqual(captured.file_bytes("manifest.json"), self.plan.manifest_bytes)
        for item in self.plan.generated_files:
            self.assertEqual(captured.file_bytes(item.relative_path), item.data)
        for row in captured.to_dict()["files"]:
            self.assertEqual(captured.file_bytes(row["path"]), (self.view / row["path"]).read_bytes())
        self.assertTrue(sibling.is_dir())
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(metadata(self.runtime), canonical)
        self.assertEqual(tree_state(self.runtime / "objects"), objects)

    def test_external_ancestor_mode_or_replacement_during_open_conflicts(self):
        """Acquisition rejects changed ancestor bindings without undoing the mutator's work."""
        canonical, objects = metadata(self.runtime), tree_state(self.runtime / "objects")
        for case in ("mode", "replacement"):
            with self.subTest(case=case):
                holder = self.parent / ("holder-" + case)
                holder.mkdir(mode=0o700)
                self.view = holder / "reading"
                self.publish()
                before = tree_state(self.view)
                moved = self.parent / ("moved-" + case)
                calls, final = 0, None
                def mutate(boundary, path):
                    """Change only the dedicated holder at its acquisition seam and record final state."""
                    nonlocal calls, final
                    if boundary == "before_open" and path == str(holder):
                        calls += 1
                        if case == "mode":
                            holder.chmod(0o500)
                        else:
                            holder.rename(moved)
                            holder.mkdir(mode=0o700)
                        final = tree_state(self.parent)
                with patch("research_pipeline.view_capture._fault", side_effect=mutate), self.assertRaises(ViewIntegrityError):
                    self.capture()
                self.assertEqual(calls, 1)
                self.assertEqual(tree_state(self.parent), final)
                retained = self.view if case == "mode" else moved / "reading"
                self.assertEqual(tree_state(retained), before)
                self.assertEqual(metadata(self.runtime), canonical)
                self.assertEqual(tree_state(self.runtime / "objects"), objects)

    def test_prior_root_membership_during_open_conflicts(self):
        """The prior root still requires its complete signature when membership changes at open."""
        self.view.chmod(0o700)
        canonical, objects = metadata(self.runtime), tree_state(self.runtime / "objects")
        calls, final = 0, None
        def mutate(boundary, path):
            """Add an in-tree directory after the root stat, retaining the resulting human state."""
            nonlocal calls, final
            if boundary == "before_open" and path == str(self.view):
                calls += 1
                (self.view / "new-directory").mkdir(mode=0o700)
                final = tree_state(self.view)
        with patch("research_pipeline.view_capture._fault", side_effect=mutate), self.assertRaises(ViewIntegrityError):
            self.capture()
        self.assertEqual(calls, 1)
        self.assertEqual(tree_state(self.view), final)
        self.assertEqual(metadata(self.runtime), canonical)
        self.assertEqual(tree_state(self.runtime / "objects"), objects)

    def test_renamed_external_ancestor_is_a_binding_conflict(self):
        """Ancestor identity changes fail even though unrelated ancestor memberships are permitted."""
        holder = self.parent / "holder"
        holder.mkdir(mode=0o700)
        self.view = holder / "reading"
        self.publish()
        def mutate(boundary, path):
            """Rename only the prior view's containing directory at the final gate."""
            if boundary == "before_final_gate":
                holder.rename(self.parent / "moved-holder")
        with patch("research_pipeline.view_capture._fault", side_effect=mutate), self.assertRaises(ViewIntegrityError):
            self.capture()
        moved = self.parent / "moved-holder/reading"
        self.assertEqual((moved / "manifest.json").read_bytes(), self.plan.manifest_bytes)

    def test_multichunk_reads_and_exact_eof_probes_for_each_pass(self):
        """Every pass consumes only declared bytes in at most 64 KiB reads and one EOF probe per file."""
        payload = bytes(range(256)) * 1024
        self.write("large.bin", payload)
        identity = (self.view / "large.bin").stat().st_ino
        real_read = os.read
        sizes = []
        def read(fd, size):
            """Record the actual large-file kernel reads without changing their contents."""
            if os.fstat(fd).st_ino == identity:
                sizes.append(size)
            return real_read(fd, size)
        with patch("os.read", side_effect=read):
            captured = self.capture()
        self.assertEqual(captured.file_bytes("large.bin"), payload)
        self.assertEqual(sizes, [65536, 65536, 65536, 65536, 1] * 2)

    def test_device_foreign_owner_and_cross_device_stat_rejection(self):
        """Real device metadata and deliberately altered stat fields fail before any unsafe open."""
        real_stat = os.stat
        device = real_stat("/dev/null")
        original = real_stat(self.view / "README.md")
        for change in ("device", "owner", "filesystem"):
            values = list(original)
            if change == "owner":
                values[4] += 1
            elif change == "filesystem":
                values[2] += 1
            replacement = device if change == "device" else os.stat_result(values)
            def observed(name, *args, **kwargs):
                """Inject entry metadata only at the parent-relative stat of the home file."""
                if name == "README.md" and kwargs.get("dir_fd") is not None:
                    return replacement
                return real_stat(name, *args, **kwargs)
            with self.subTest(change=change), patch("os.stat", side_effect=observed), self.assertRaises(ViewLayoutError):
                self.capture()

    def test_disappearance_after_enumeration_is_conflict(self):
        """A selected entry disappearing during acquisition is never an ordinary missing target."""
        self.view.chmod(0o700)
        def mutate(boundary, path):
            """Remove the already enumerated home immediately before its no-follow open."""
            if boundary == "before_open" and path == "README.md":
                (self.view / path).unlink()
        with patch("research_pipeline.view_capture._fault", side_effect=mutate), self.assertRaises(ViewIntegrityError):
            self.capture()
        self.assertFalse((self.view / "README.md").exists())

    def test_pipe_coordinated_process_edits_earlier_file_during_later_read(self):
        """A real separate editor changes previously read bytes only after a later read is underway."""
        home = self.view / "README.md"
        home.chmod(0o600)
        program = '''
import sys
from pathlib import Path
assert sys.stdin.buffer.read(1) == b"x"
Path(sys.argv[1]).write_bytes(b"separate-process human work")
sys.stdout.buffer.write(b"y")
sys.stdout.buffer.flush()
'''
        process = subprocess.Popen([sys.executable, "-B", "-c", program, str(home)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=child_environment())
        def cleanup():
            """Reap the mutator even if a bounded handshake or assertion fails."""
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
        self.addCleanup(cleanup)
        read_home, mutated = False, False
        def coordinate(boundary, path):
            """Use a pipe and selector, never a sleep, to establish mutation ordering."""
            nonlocal read_home, mutated
            if boundary == "file_read" and path == "README.md":
                read_home = True
            if boundary == "chunk_read" and path != "README.md" and read_home and not mutated:
                mutated = True
                process.stdin.write(b"x")
                process.stdin.flush()
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(timeout=10), "mutator handshake timed out")
                self.assertEqual(process.stdout.read(1), b"y")
        with patch("research_pipeline.view_capture._fault", side_effect=coordinate), self.assertRaises(ViewIntegrityError):
            self.capture()
        self.assertTrue(mutated)
        self.assertEqual(home.read_bytes(), b"separate-process human work")
        self.assertEqual(process.wait(timeout=10), 0)

    def test_faults_close_all_acquired_descriptors_and_retain_causes(self):
        """Initial/final EIO and EMFILE failures after divergence cannot produce partial success."""
        self.write("README.md", b"already diverged")
        for operation in ("open", "stat", "fstat", "scandir", "read", "close"):
            for late in (False, True):
                if operation == "open" and late:
                    continue  # The final gate intentionally reuses all held descriptors.
                with self.subTest(operation=operation, late=late):
                    before = tree_state(self.view)
                    acquired, closed = set(), set()
                    real_open, real_close = os.open, os.close
                    original = getattr(os, operation)
                    active, failed = not late, False
                    def opening(*args, **kwargs):
                        """Track acquired descriptors without changing their kernel behavior."""
                        fd = real_open(*args, **kwargs)
                        acquired.add(fd)
                        return fd
                    def closing(fd):
                        """Actually close once, then optionally simulate lost close acknowledgment."""
                        nonlocal failed
                        real_close(fd)
                        closed.add(fd)
                        if operation == "close" and not failed:
                            failed = True
                            raise OSError(errno.EIO, "injected close failure")
                    def fault(*args, **kwargs):
                        """Fail a single actual I/O boundary; all later cleanup remains real."""
                        nonlocal failed
                        if active and not failed:
                            failed = True
                            raise OSError(errno.EMFILE if operation == "open" else errno.EIO, "injected operation failure")
                        return original(*args, **kwargs)
                    def arm(boundary, path):
                        """Arm final-pass failures only after all safe divergent bytes were observed."""
                        nonlocal active
                        if boundary == "before_final_gate":
                            active = True
                    with patch("os.open", side_effect=opening), patch("os.close", side_effect=closing), \
                         patch("research_pipeline.view_capture._fault", side_effect=arm):
                        if operation == "close":
                            with self.assertRaises(ViewOperationalError) as caught:
                                self.capture()
                        else:
                            with patch("os." + operation, side_effect=fault), self.assertRaises(ViewOperationalError) as caught:
                                self.capture()
                    self.assertIsInstance(caught.exception.__cause__, OSError)
                    self.assertEqual(acquired, closed)
                    self.assertEqual(tree_state(self.view), before)

    def test_process_termination_leaves_input_and_canonical_state_intact(self):
        """Termination after a real read has no persistent capture protocol or cleanup side effect."""
        before, canonical = tree_state(self.view), metadata(self.runtime)
        plan_file = self.parent / "independent-plan.json"
        plan_file.write_bytes(self.plan.manifest_bytes)
        program = '''
import os, sys
from pathlib import Path
from research_pipeline.view_plan import readable_plan_from_manifest
from research_pipeline.view_capture import capture_readable_view
from tests.view_capture_fixtures import capture_limits, SOURCE
import research_pipeline.view_capture as capture
budgets = capture_limits()
plan = readable_plan_from_manifest(Path(sys.argv[2]).read_bytes(), limits=budgets.plan_limits)
def stop(boundary, path):
    """Terminate after one real file capture, before any successful return."""
    if boundary == "file_read":
        os._exit(77)
capture._fault = stop
capture_readable_view(sys.argv[1], expected_plan=plan, source_root=SOURCE,
                      protected_roots=[sys.argv[3]], limits=budgets)
'''
        result = subprocess.run([sys.executable, "-B", "-c", program, str(self.view), str(plan_file), str(self.runtime)],
            env=child_environment(), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertEqual(tree_state(self.view), before)
        self.assertEqual(metadata(self.runtime), canonical)
