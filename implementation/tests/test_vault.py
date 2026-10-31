"""Protected independent generations and bounded offline observations over disposable stores."""

from dataclasses import replace
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline.domain import ArtifactReference, DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError, _canonical
from research_pipeline.store import RecordStore, StoreClosedError
from research_pipeline.view_plan import (
    ViewPlanError, plan_readable_snapshot, readable_plan_from_manifest,
)
from research_pipeline.vault import (
    ViewError, ViewLayoutError, ViewIntegrityError, ViewOperationalError,
    materialize_readable_view, inspect_readable_view,
)
from tests.snapshot_fixtures import limits, selection, simple_project, populated
from tests.test_assessment_store import metadata
from tests.test_store import record, request
from tests.test_view_plan import emitted_navigation, forged_plan, README_FIELDS


SOURCE = Path(__file__).resolve().parents[2]


def restore_directories(root):
    """Restore only disposable fixture directory permissions for test cleanup, never follow symlinks."""
    for current, children, _ in os.walk(root, followlinks=False):
        os.chmod(current, 0o700)
        for name in children:
            child = Path(current) / name
            if not child.is_symlink():
                child.chmod(0o700)


def child_environment():
    """Select this candidate's package and fixtures without installed imports or bytecode writes."""
    return {**os.environ, "PYTHONPATH": os.pathsep.join((str(SOURCE / "implementation/src"),
                                                       str(SOURCE / "implementation"))),
            "PYTHONDONTWRITEBYTECODE": "1"}


def paired_payload(attempt):
    """Locate a retained sibling by token, requiring any recorded intent to agree exactly."""
    token = attempt.name.removeprefix(".readable-view-")
    name = ".readable-generation-" + token
    intent_path = attempt / "intent.json"
    if intent_path.exists():
        intent = json.loads(intent_path.read_bytes())
        assert intent["token"] == token and intent["generation_name"] == name
    return attempt.parent / name


class ManifestTests(unittest.TestCase):
    """Pure reconstruction rejects untrusted budgets and rehashed noncanonical rendered content."""

    def setUp(self):
        """Capture minimal metadata in a disposable store; pure tests need no external destination."""
        temporary = TemporaryDirectory(prefix="manifest-test-")
        self.addCleanup(temporary.cleanup)
        with RecordStore.create(Path(temporary.name) / "runtime") as store:
            simple_project(store)
            self.plan = plan_readable_snapshot(store.capture_snapshot(selection(), limits=limits()))

    def test_exact_reconstruction_and_caller_allowances(self):
        """Canonical reconstruction preserves every byte and refuses any excessive embedded allowance."""
        self.assertEqual(readable_plan_from_manifest(self.plan.manifest_bytes, limits=limits()), self.plan)
        for name, value in limits().to_dict().items():
            if value:
                with self.subTest(name=name), self.assertRaises(SnapshotLimitError):
                    readable_plan_from_manifest(self.plan.manifest_bytes, limits=replace(limits(), **{name: value - 1}))
        with self.assertRaises(DomainValidationError):
            readable_plan_from_manifest(bytearray(self.plan.manifest_bytes), limits=limits())

    def test_strict_descriptor_schema_and_numeric_types(self):
        """Duplicate keys, unknown fields, versions, coercions and changed projections never reconstruct."""
        def change(value, field, replacement):
            """Create one canonical deliberate descriptor mutation without editing the retained plan."""
            value[field] = replacement
            return _canonical(value).encode("ascii")

        malformed = [b'{"format":1,"format":2}', self.plan.manifest_bytes + b" ", b"\xff"]
        for field, replacement in (("format", "unsupported"), ("unexpected", 1), ("plan_id", "a" * 64)):
            malformed.append(change(self.plan.to_dict(), field, replacement))
        for field in ("max_files", "max_records", "max_roots"):
            value = self.plan.to_dict()
            value["limits"][field] = True
            malformed.append(_canonical(value).encode())
        for field in ("page_path", "projection_limitation", "unexpected"):
            value = self.plan.to_dict()
            value["records"][0][field] = "forged"
            malformed.append(_canonical(value).encode())
        for data in malformed:
            with self.subTest(data=data[:60]), self.assertRaises((ViewPlanError, DomainValidationError)):
                readable_plan_from_manifest(data, limits=limits())
        with patch("research_pipeline.view_plan._strict_json", side_effect=AssertionError("decode forbidden")), \
             self.assertRaises(SnapshotLimitError):
            readable_plan_from_manifest(b"x" * 100, limits=limits(max_file_bytes=99))

    def test_noncanonical_rendered_prose_rejected_despite_rehashed_inventory(self):
        """A self-consistently rehashed altered page cannot replace the single deterministic renderer."""
        home = next(f.data for f in self.plan.generated_files if f.relative_path == "README.md")
        forged = forged_plan(self.plan, {"README.md": home + b"\nInvented prose.\n"})
        with self.assertRaises(ViewPlanError):
            readable_plan_from_manifest(forged.manifest_bytes, limits=limits())


class VaultFixture(unittest.TestCase):
    """Shared external private fixture and bounded process helpers, with no inherited test cases."""

    def setUp(self):
        """Use an explicit external temporary parent so confinement is exercised unchanged."""
        temporary = TemporaryDirectory(prefix="vault-tests-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.parent.chmod(0o700)
        self.addCleanup(restore_directories, self.parent)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)
        self.artifact = self.store.put_artifact(b"shared synthetic bytes\n")
        self.store.submit(request("project", [record("project", kind="project",
            artifact_references=[self.artifact, self.artifact])]))
        self.plan = plan_readable_snapshot(self.store.capture_snapshot(selection(), limits=limits()))
        self.destination = self.parent / "reading"

    def publish(self, path=None, plan=None, **options):
        """Materialize with explicit exclusions and a finite complete enumeration allowance."""
        return materialize_readable_view(self.store, plan or self.plan, path or self.destination,
            source_root=SOURCE, protected_roots=[], max_entries=4096, **options)

    def inspect(self, path=None, **options):
        """Inspect without using the open store, retaining an independent expected plan identity."""
        return inspect_readable_view(path or self.destination, limits=limits(), max_entries=4096,
                                     expected_plan_id=self.plan.plan_id, **options)

    def child(self, program, *args, expected=0):
        """Execute a bounded fresh source-local process and retain useful failure diagnostics."""
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, args)],
            cwd=self.parent, env=child_environment(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def codes(self):
        """Return observed path/code pairs while requiring an explicitly divergent result."""
        result = self.inspect()
        self.assertEqual(result.status, "diverged")
        self.assertEqual(result.differences, tuple(sorted(result.differences)))
        self.assertTrue(all(len(d.detail) <= 240 for d in result.differences))
        return {(d.relative_path, d.code) for d in result.differences}


class VaultTests(VaultFixture):
    """Exercise real independent copies, unchanged metadata, confinement and offline divergence."""

    def test_independent_bytes_and_offline_inspection(self):
        """Two publications retain paired evidence, identical portable bytes and disjoint protected inodes."""
        before = metadata(self.root)
        with patch.object(RecordStore, "_transaction", side_effect=AssertionError("metadata read")):
            first = self.publish()
            second = self.publish(self.parent / "second")
        self.assertEqual(first.verification, "verified_at_materialization")
        self.assertEqual(first.plan_id, second.plan_id)
        source_ids = {(p.stat().st_dev, p.stat().st_ino) for p in (self.root / "objects").iterdir()}
        seen = set(source_ids)
        for root in (self.destination, self.parent / "second"):
            for entry in (*self.plan.generated_files, *self.plan.artifact_copies):
                path = root / entry.relative_path
                expected = entry.data if hasattr(entry, "data") else self.store.read_artifact(ArtifactReference(entry.digest, entry.size))
                self.assertEqual(path.read_bytes(), expected)
                info = path.stat()
                self.assertEqual(stat.S_IMODE(info.st_mode), 0o400)
                self.assertEqual(info.st_nlink, 1)
                self.assertNotIn((info.st_dev, info.st_ino), seen)
                seen.add((info.st_dev, info.st_ino))
            for directory in self.plan.directories:
                self.assertEqual(stat.S_IMODE((root / directory.relative_path).stat().st_mode), 0o500)
        attempt = Path(first.attempt_path)
        self.assertEqual({p.name for p in attempt.iterdir()}, {"intent.json", "ready.json", "published.json"})
        intent = json.loads((attempt / "intent.json").read_bytes())
        self.assertFalse(paired_payload(attempt).exists())
        self.assertEqual(intent["generation"], list((self.destination.stat().st_dev, self.destination.stat().st_ino)))
        self.assertEqual(metadata(self.root), before)
        self.store.close()
        self.root.rename(self.parent / "unavailable-runtime")
        output = self.child('''
import sys
from research_pipeline.vault import inspect_readable_view
from tests.snapshot_fixtures import limits
result = inspect_readable_view(sys.argv[1], limits=limits(), max_entries=4096, expected_plan_id=sys.argv[2])
assert result.status == "verified" and result.differences == ()
print(result.plan_id)
''', self.destination, self.plan.plan_id)
        self.assertIn(self.plan.plan_id, output)

    def test_populated_actual_navigation_and_historical_selection(self):
        """Actual disk pages preserve all routes, seven-field READMEs and captured old revisions."""
        with RecordStore.create(self.parent / "dossier") as store:
            chosen, payloads = populated(store, self.parent)
            snapshot = store.capture_snapshot(chosen, limits=limits())
            plan = plan_readable_snapshot(snapshot)
            before = metadata(self.parent / "dossier")
            result = materialize_readable_view(store, plan, self.destination,
                source_root=SOURCE, protected_roots=[], max_entries=4096)
            self.assertEqual(metadata(self.parent / "dossier"), before)
        generated = tuple(replace(file, data=(self.destination / file.relative_path).read_bytes())
                          for file in plan.generated_files)
        actual = replace(plan, generated_files=generated)
        pages, graph = emitted_navigation(actual)
        entries = {r["record_id"]: r for r in plan.to_dict()["records"]}
        claim, product = (entries[key]["page_path"] for key in ("candidate", "native-product"))
        self.assertIn(claim, [target for target, _ in graph["README.md"]])
        self.assertIn(product, [target for target, _ in graph[claim]])
        for identity in ("review-a", "review-b", "claim-objection", "route"):
            self.assertIn(entries[identity]["page_path"], [target for target, _ in graph[claim]])
        self.assertIn(entries["capture"]["page_path"], [target for target, _ in graph[product]])
        for mapping in plan.to_dict()["mappings"]:
            data = (self.destination / mapping["relative_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), mapping["digest"])
            if mapping["logical_key"]["record_id"] == "capture":
                self.assertEqual(data, payloads[mapping["details"]["path"]])
            if mapping["logical_key"]["record_id"] == "native-product":
                self.assertIn(mapping["relative_path"], [target for target, _ in graph[product]])
        for page, headings in pages.items():
            if page.endswith("README.md"):
                self.assertTrue(README_FIELDS <= set(headings))
            for target, fragment in graph[page]:
                self.assertTrue((self.destination / target).is_file())
                if fragment:
                    self.assertIn(fragment, [h.lower().replace(" ", "-").replace("/", "") for h in pages[target]])
        self.assertEqual(inspect_readable_view(self.destination, limits=limits(), max_entries=4096,
                         expected_plan_id=result.plan_id).status, "verified")
        self.assertEqual(json.loads(entries["candidate"]["envelope_json"])["scientific_disposition"], "provisional")
        self.assertTrue(any(r["classification"]["category"] == "generic" for r in entries.values()))

    def test_edit_shared_mapping_isolation(self):
        """Editing one same-digest mapping changes neither its sibling, another generation nor the store."""
        self.publish()
        self.publish(self.parent / "second")
        before = metadata(self.root)
        entry, sibling = self.plan.artifact_copies
        path = self.destination / entry.relative_path
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(b"edited local copy\n")
        codes = self.codes()
        self.assertTrue({(entry.relative_path, "mode"), (entry.relative_path, "size"),
                         (entry.relative_path, "digest")} <= codes)
        self.assertEqual((self.destination / sibling.relative_path).read_bytes(), original)
        self.assertEqual((self.parent / "second" / entry.relative_path).read_bytes(), original)
        self.assertEqual(self.store.read_artifact(self.artifact), original)
        self.assertEqual(metadata(self.root), before)

    def test_modes_umasks_and_owner_mask_failure(self):
        """Explicit output modes survive ordinary umasks; masked owner bits retain a failed attempt."""
        for mask in (0, 0o22, 0o77, 0o700):
            output = self.child('''
import os,sys
from research_pipeline.store import RecordStore
from research_pipeline.view_plan import readable_plan_from_manifest
from research_pipeline.vault import materialize_readable_view, ViewOperationalError
from tests.snapshot_fixtures import limits
from pathlib import Path
plan = readable_plan_from_manifest(Path(sys.argv[2]).read_bytes(), limits=limits())
with RecordStore.open(sys.argv[1]) as store:
    old = os.umask(int(sys.argv[5]))
    try:
        try:
            result = materialize_readable_view(store, plan, sys.argv[3], source_root=sys.argv[4], protected_roots=[], max_entries=4096)
        except ViewOperationalError:
            assert int(sys.argv[5]) == 0o700
            assert not Path(sys.argv[3]).exists()
        else:
            assert int(sys.argv[5]) != 0o700
            assert all((Path(sys.argv[3])/d.relative_path).stat().st_mode & 0o777 == 0o500 for d in plan.directories)
            assert all((Path(sys.argv[3])/f.relative_path).stat().st_mode & 0o777 == 0o400 for f in (*plan.generated_files,*plan.artifact_copies))
        observed = os.umask(old)
        assert observed == int(sys.argv[5]), "product changed process umask"
    finally:
        os.umask(old)
''', self.root, self.save_manifest(), self.parent / ("mask-" + str(mask)), SOURCE, mask)
            self.assertEqual(output, "")

    def save_manifest(self):
        """Persist canonical bytes as a private process fixture, outside the portable view."""
        path = self.parent / "plan.json"
        path.write_bytes(self.plan.manifest_bytes)
        path.chmod(0o600)
        return path

    def test_destination_rejections_preserve_existing_entries(self):
        """Files, empty/edited directories, aliases, dangling links and unsafe ancestors remain untouched."""
        for kind in ("file", "directory", "symlink", "alias"):
            target = self.parent / ("Reading" if kind == "alias" else "reading")
            if kind == "directory":
                target.mkdir(mode=0o700)
            elif kind == "symlink":
                target.symlink_to("absent")
            else:
                target.write_bytes(b"unrelated")
            before = target.lstat()
            with self.assertRaises(ViewLayoutError):
                self.publish()
            self.assertEqual(target.lstat(), before)
            target.rmdir() if kind == "directory" else target.unlink()
        self.publish()
        with self.assertRaises(ViewLayoutError):
            self.publish()
        link = self.parent / "linked"
        link.symlink_to(self.parent, target_is_directory=True)
        with self.assertRaises(ViewLayoutError):
            self.publish(link / "new")
        for path in (self.parent / ".." / "bad", self.parent / "CON", self.parent / "bad."):
            with self.assertRaises((ViewLayoutError, DomainValidationError)):
                self.publish(path)

    def test_exclusions_and_recognizable_layouts(self):
        """Excluded roots and recognizable layouts, including empty reservations, reject nested output."""
        for excluded in (self.root, SOURCE, SOURCE / "implementation", self.parent / "backup", self.parent / "control"):
            for destination in (excluded, excluded / "child", excluded.parent):
                with self.subTest(destination=destination), self.assertRaises(ViewLayoutError):
                    materialize_readable_view(self.store, self.plan, destination, source_root=SOURCE,
                                             protected_roots=[excluded], max_entries=4096)
        for marker in ("metadata.sqlite3", "snapshot.sqlite3", ".work-product", "manifest.json", "intent.json"):
            parent = self.parent / ("layout-" + marker.replace(".", "x"))
            parent.mkdir(mode=0o700)
            (parent / marker).write_bytes(b"not read")
            with self.assertRaises(ViewLayoutError):
                self.publish(parent / "child")
        for prefix in (".readable-view-", ".readable-generation-"):
            parent = self.parent / (prefix + "b" * 32)
            parent.mkdir(mode=0o700)
            with self.assertRaises(ViewLayoutError):
                self.publish(parent / "child")
            self.assertEqual(list(parent.iterdir()), [])
        self.parent.chmod(0o755)
        with self.assertRaises(ViewLayoutError):
            self.publish()
        self.parent.chmod(0o700)

    def test_bounds_and_forged_plan_fail_before_reservation(self):
        """Counts, ordinary integer limits and bypassed frozen values fail before reading or constructing output."""
        for invalid in (True, 0, -1, 1.0, "2", 2**63):
            with self.assertRaises(DomainValidationError):
                materialize_readable_view(self.store, self.plan, self.destination, source_root=SOURCE,
                                         protected_roots=[], max_entries=invalid)
        with self.assertRaises(SnapshotLimitError):
            materialize_readable_view(self.store, self.plan, self.destination, source_root=SOURCE,
                                     protected_roots=[], max_entries=1)
        home = next(f.data for f in self.plan.generated_files if f.relative_path == "README.md")
        with self.assertRaises(ViewPlanError):
            self.publish(plan=forged_plan(self.plan, {"README.md": home + b"\nInvented.\n"}))
        self.assertFalse(list(self.parent.glob(".readable-view-*")))
        self.store.close()
        with self.assertRaises(StoreClosedError):
            self.publish()

    def test_missing_corrupt_and_unsafe_sources(self):
        """Source failures retain attempts but never publish or repair canonical corruption or unsafe types."""
        path = self.root / "objects" / self.artifact.digest
        original = path.read_bytes()
        before = metadata(self.root)
        for kind in ("missing", "corrupt", "truncated", "symlink", "fifo", "directory", "writable"):
            path.unlink()
            if kind in ("corrupt", "truncated", "writable"):
                path.write_bytes(b"!" * len(original) if kind == "corrupt" else original[:1] if kind == "truncated" else original)
                path.chmod(0o600 if kind == "writable" else 0o400)
            elif kind == "symlink":
                path.symlink_to(self.parent / "absent")
            elif kind == "fifo":
                os.mkfifo(path, 0o400)
            elif kind == "directory":
                path.mkdir(mode=0o700)
            with self.subTest(kind=kind), self.assertRaises(ViewError):
                self.publish()
            self.assertFalse(self.destination.exists())
            self.assertEqual(metadata(self.root), before)
            if kind == "directory":
                path.rmdir()
            elif kind != "missing":
                path.unlink()
            path.write_bytes(original)
            path.chmod(0o400)
        self.assertEqual(len(list(self.parent.glob(".readable-view-*"))), 7)

    def test_source_staging_hardlink_and_empty_artifact(self):
        """Canonical staging links are legitimate; every empty/repeated output still has an independent inode."""
        os.link(self.root / "objects" / self.artifact.digest, self.root / ".staging" / "retained")
        empty = self.store.put_artifact(b"")
        self.store.submit(request("empty", [record("project", 2, "project", artifact_references=[empty, empty])], {"project": 1}))
        self.publish()
        plan = plan_readable_snapshot(self.store.capture_snapshot(selection(), limits=limits()))
        self.publish(self.parent / "empty", plan)
        for entry in plan.artifact_copies:
            path = self.parent / "empty" / entry.relative_path
            self.assertEqual(path.read_bytes(), b"")
            self.assertEqual(path.stat().st_nlink, 1)

    def test_inspection_missing_extra_renamed_types_and_hardlinks(self):
        """Unsafe entries are reported without traversal, and renamed files yield missing plus extra."""
        self.publish()
        relative = self.plan.artifact_copies[0].relative_path
        path = self.destination / relative
        path.parent.chmod(0o700)
        path.rename(path.with_name("renamed"))
        self.assertTrue({(relative, "missing"), (str(Path(relative).with_name("renamed")), "extra")} <= self.codes())
        path.with_name("renamed").rename(path)
        for kind in ("symlink", "fifo", "directory", "hardlink"):
            path.unlink()
            if kind == "symlink":
                path.symlink_to(self.root)
            elif kind == "fifo":
                os.mkfifo(path, 0o400)
            elif kind == "directory":
                path.mkdir(mode=0o700)
            else:
                os.link(self.destination / self.plan.artifact_copies[1].relative_path, path)
            self.assertIn((relative, "hardlink" if kind == "hardlink" else "type"), self.codes())
            path.rmdir() if kind == "directory" else path.unlink()
            path.write_bytes(b"shared synthetic bytes\n")
            path.chmod(0o400)

    def test_manifest_errors_pins_and_inspection_limits(self):
        """Missing/unsafe/malformed descriptors and independent pin mismatches raise explicit errors."""
        self.publish()
        with self.assertRaises(ViewIntegrityError):
            inspect_readable_view(self.destination, limits=limits(), max_entries=4096, expected_plan_id="a" * 64)
        with self.assertRaises(SnapshotLimitError):
            inspect_readable_view(self.destination, limits=limits(), max_entries=1)
        descriptor = self.destination / "manifest.json"
        descriptor.chmod(0o600)
        self.assertIn(("manifest.json", "mode"), self.codes())
        descriptor.write_bytes(b"{}")
        with self.assertRaises(ViewPlanError):
            self.inspect()
        self.destination.chmod(0o700)
        descriptor.unlink()
        with self.assertRaises(ViewLayoutError):
            self.inspect()

    def test_inspection_observed_mutations_at_final_gate(self):
        """Replacement/addition and in-place edits after reads cannot return a verified observation."""
        self.publish()
        for target in ("README.md", "manifest.json", self.plan.artifact_copies[0].relative_path):
            path = self.destination / target
            original = path.read_bytes()

            def seam(point):
                """Mutate the already-read inode at the private final inspection seam."""
                if point == "inspection_before_final":
                    path.chmod(0o600)
                    path.write_bytes(original + b"changed")

            with patch("research_pipeline.vault._fault", side_effect=seam):
                self.assertIn((target, "changed_during_inspection"), self.codes())
            path.write_bytes(original)
            path.chmod(0o400)

    def test_inspection_read_only_and_import_inert(self):
        """Fresh offline inspection does not write, open databases, launch programs or access a network."""
        self.publish()
        self.store.close()
        self.child('''
import os,sys

def audit(event, args):
    """Reject filesystem mutation, process launches, database access and sockets in the observed operation."""
    if event in ("os.chmod", "os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.link", "os.symlink", "os.truncate") or event.startswith(("sqlite3.", "subprocess.", "socket.")):
        raise AssertionError(event)
    if event == "open" and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
        raise AssertionError("write open")
sys.addaudithook(audit)
from research_pipeline.vault import inspect_readable_view
from tests.snapshot_fixtures import limits
assert inspect_readable_view(sys.argv[1], limits=limits(), max_entries=4096).status == "verified"
''', self.destination)

    def test_documented_example(self):
        """Run the exact self-contained published block in a fresh candidate-source interpreter."""
        text = (SOURCE / "docs/readable-snapshots.md").read_text()
        program = text.split("## Runnable local example\n", 1)[1].split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)


class OfflineInspectionTests(unittest.TestCase):
    """Exercise the inspector on explicitly assembled canonical fixtures, without claiming publication."""

    def setUp(self):
        """Assemble one bounded offline tree from canonical plan bytes in a disposable permitted area."""
        temporary = TemporaryDirectory(prefix="offline-view-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.addCleanup(restore_directories, self.parent)
        self.data = b"inert" * 15000
        with RecordStore.create(self.parent / "runtime") as store:
            artifact = store.put_artifact(self.data)
            store.submit(request("initial", [record("project", kind="project", artifact_references=[artifact])]))
            self.plan = plan_readable_snapshot(store.capture_snapshot(selection(), limits=limits()))
        self.root = self.parent / "reading"
        for directory in self.plan.directories:
            (self.root / directory.relative_path).mkdir(mode=0o700)
        for file in self.plan.generated_files:
            path = self.root / file.relative_path
            path.write_bytes(file.data)
            path.chmod(0o400)
        for file in self.plan.artifact_copies:
            path = self.root / file.relative_path
            path.write_bytes(self.data)
            path.chmod(0o400)
        for directory in reversed(self.plan.directories):
            (self.root / directory.relative_path).chmod(0o500)

    def inspect(self):
        """Compare a fixture with an independent plan pin and explicit caller allowances."""
        return inspect_readable_view(self.root, limits=limits(), max_entries=4096, expected_plan_id=self.plan.plan_id)

    def test_verified_and_bounded_streaming(self):
        """A complete canonical offline fixture verifies using reads no larger than 64 KiB."""
        real_read = os.read
        sizes = []

        def read(fd, size):
            """Observe actual read requests without substituting bytes or changing filesystem behavior."""
            sizes.append(size)
            return real_read(fd, size)

        with patch("research_pipeline.vault.os.read", side_effect=read):
            result = self.inspect()
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.differences, ())
        self.assertEqual(max(sizes), 65536)
        self.assertIn(1, sizes)

    def test_edited_generated_original_and_mode(self):
        """Owned writable generated and original files yield content and mode differences."""
        for relative in ("README.md", self.plan.artifact_copies[0].relative_path):
            path = self.root / relative
            path.chmod(0o600)
            path.write_bytes(b"edited")
        result = self.inspect()
        self.assertEqual(result.status, "diverged")
        codes = {(d.relative_path, d.code) for d in result.differences}
        for relative in ("README.md", self.plan.artifact_copies[0].relative_path):
            self.assertTrue({(relative, "mode"), (relative, "size"), (relative, "digest")} <= codes)

    def test_unsafe_entries_and_missing_extra(self):
        """Symlinks/FIFOs/directories and hardlinks are reported without reading unsafe targets."""
        relative = self.plan.artifact_copies[0].relative_path
        path = self.root / relative
        path.parent.chmod(0o700)
        path.rename(path.parent / "renamed")
        result = self.inspect()
        self.assertIn((relative, "missing"), {(d.relative_path, d.code) for d in result.differences})
        self.assertTrue(any(d.code == "extra" and d.relative_path.endswith("renamed") for d in result.differences))
        path.symlink_to(self.parent / "runtime")
        self.assertIn((relative, "type"), {(d.relative_path, d.code) for d in self.inspect().differences})
        path.unlink()
        os.mkfifo(path, 0o400)
        self.assertIn((relative, "type"), {(d.relative_path, d.code) for d in self.inspect().differences})
        path.unlink()
        os.link(path.parent / "renamed", path)
        self.assertIn((relative, "hardlink"), {(d.relative_path, d.code) for d in self.inspect().differences})

    def test_directory_substitution_at_final_gate(self):
        """An expected child replaced by a symlink after reads is detected through held descriptors."""
        self.root.chmod(0o700)
        child = self.root / "brief"

        def seam(point):
            """Move the held child and replace its name without following the new target."""
            if point == "inspection_before_final":
                child.rename(self.root / "moved")
                child.symlink_to(self.parent / "runtime", target_is_directory=True)

        with patch("research_pipeline.vault._fault", side_effect=seam):
            result = self.inspect()
        self.assertEqual(result.status, "diverged")
        self.assertTrue(any(d.code == "changed_during_inspection" for d in result.differences))

    def test_root_replacement_at_final_gate(self):
        """An inspection pinned to one root cannot silently succeed after the public binding moves."""
        def seam(point):
            """Replace only the root binding, retaining the pinned inode for honest comparison."""
            if point == "inspection_before_final":
                self.root.rename(self.parent / "moved")
                self.root.mkdir(mode=0o700)

        with patch("research_pipeline.vault._fault", side_effect=seam):
            result = self.inspect()
        self.assertEqual(result.status, "diverged")
        self.assertTrue(any(d.code == "changed_during_inspection" for d in result.differences))

    def test_manifest_substitution_and_file_mutation_during_reads(self):
        """Descriptor races raise specific errors; later content races return explicit changed observations."""
        original = self.root / self.plan.artifact_copies[0].relative_path
        changed = False

        def seam(point):
            """Mutate an original on its actual chunk boundary, after descriptor reconstruction has completed."""
            nonlocal changed
            if point == "inspection_after_manifest":
                changed = True
            elif point == "inspection_chunk" and changed:
                changed = False
                original.chmod(0o600)
                original.write_bytes(b"mutated")

        with patch("research_pipeline.vault._fault", side_effect=seam):
            self.assertEqual(self.inspect().status, "diverged")
        self.root.chmod(0o700)
        descriptor = self.root / "manifest.json"
        replaced = False

        def replace_manifest(point):
            """Substitute a same-byte descriptor inode while the initial descriptor is being read."""
            nonlocal replaced
            if point == "inspection_chunk" and not replaced:
                replaced = True
                descriptor.unlink()
                descriptor.write_bytes(self.plan.manifest_bytes)
                descriptor.chmod(0o400)

        with patch("research_pipeline.vault._fault", side_effect=replace_manifest), self.assertRaises(ViewIntegrityError):
            self.inspect()

    def test_excess_entries_and_actual_bytes_raise_limits(self):
        """Finite tree enumeration and actual-file budgets fail explicitly rather than return partial success."""
        expected = len(self.plan.generated_files) + len(self.plan.artifact_copies) + len(self.plan.directories) - 1
        self.assertEqual(inspect_readable_view(self.root, limits=limits(), max_entries=expected).status, "verified")
        with self.assertRaises(SnapshotLimitError):
            inspect_readable_view(self.root, limits=limits(), max_entries=expected - 1)
        self.root.chmod(0o700)
        (self.root / "extra").write_bytes(b"inert")
        with self.assertRaises(SnapshotLimitError):
            inspect_readable_view(self.root, limits=limits(), max_entries=expected)

    def test_foreign_owner_is_reported_without_reading(self):
        """An unsafe ownership observation is reported before any open of that selected child."""
        relative = self.plan.artifact_copies[0].relative_path
        name = Path(relative).name
        real_stat, real_open = os.stat, os.open

        def foreign(path, *args, **kwargs):
            """Inject only the selected leaf's ownership observation; all actual directory reads remain real."""
            info = real_stat(path, *args, **kwargs)
            if path == name:
                fields = list(info)
                fields[4] = os.geteuid() + 1
                return os.stat_result(fields)
            return info

        def guarded_open(path, *args, **kwargs):
            """Fail if the inspector tries reading a leaf it already knows is foreign-owned."""
            self.assertNotEqual(path, name)
            return real_open(path, *args, **kwargs)

        with patch("research_pipeline.vault.os.stat", side_effect=foreign), \
             patch("research_pipeline.vault.os.open", side_effect=guarded_open):
            result = self.inspect()
        self.assertIn((relative, "owner"), {(d.relative_path, d.code) for d in result.differences})

    def test_directory_descriptor_exhaustion_is_an_error(self):
        """Descriptor exhaustion while opening an expected subtree raises rather than returns partial observations."""
        import errno
        real_open = os.open

        def exhausted(path, *args, **kwargs):
            """Simulate an actual EMFILE only at an expected child directory open."""
            if path == "brief":
                raise OSError(errno.EMFILE, "injected descriptor exhaustion")
            return real_open(path, *args, **kwargs)

        with patch("research_pipeline.vault.os.open", side_effect=exhausted), self.assertRaises(ViewOperationalError):
            self.inspect()

    def final_binding_stat(self, number):
        """Inject one errno at the final ancestor-binding stat after all real content checks."""
        real_stat = os.stat
        armed = reached = False

        def seam(point):
            """Arm only after enumeration, descriptor reconstruction and content reads finish."""
            nonlocal armed
            if point == "inspection_before_final":
                armed = True

        def binding_stat(path, *args, **kwargs):
            """Fail only the held external parent's binding stat in _Directories.check."""
            nonlocal reached
            if armed and path == self.parent.name and kwargs.get("dir_fd") is not None:
                reached = True
                raise OSError(number, "injected final ancestor stat")
            return real_stat(path, *args, **kwargs)

        try:
            with patch("research_pipeline.vault._fault", side_effect=seam), \
                 patch("research_pipeline.vault.os.stat", side_effect=binding_stat):
                return self.inspect()
        finally:
            self.assertTrue(reached, "final ancestor binding stat was not reached")

    def assert_errno_cause(self, error, number):
        """Require the original OS errno to remain reachable through translated exception causes."""
        while error is not None:
            if isinstance(error, OSError) and error.errno == number:
                return
            error = error.__cause__
        self.fail(f"missing injected errno {number} in cause chain")

    def test_final_binding_stat_operational_errors_propagate(self):
        """I/O and resource failures at the final guard abort even after real differences were collected."""
        (self.root / "README.md").chmod(0o600)
        for number in (errno.EIO, errno.EMFILE, errno.ENFILE, errno.ENOMEM, errno.EBADF):
            with self.subTest(errno=number), self.assertRaises(ViewOperationalError) as caught:
                self.final_binding_stat(number)
            self.assert_errno_cause(caught.exception, number)

    def test_final_binding_stat_observed_changes_diverge(self):
        """Missing or inaccessible ancestor bindings still yield explicit final-gate divergence."""
        for number in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ESTALE, errno.EACCES, errno.EPERM):
            with self.subTest(errno=number):
                result = self.final_binding_stat(number)
                self.assertEqual(result.status, "diverged")
                self.assertIn(("", "changed_during_inspection"),
                              {(d.relative_path, d.code) for d in result.differences})

    def test_final_guard_raw_fstat_operational_error_propagates(self):
        """A raw ancestor fstat failure after real directory binding checks remains an operational error."""
        from research_pipeline.checkout import _Directories

        real_check, real_fstat = _Directories.check, os.fstat
        armed = checked = reached = False
        ancestor = self.parent.stat()

        def seam(point):
            """Enable injection at the final seam while keeping all earlier reads and checks real."""
            nonlocal armed
            if point == "inspection_before_final":
                armed = True

        def check(directories):
            """Perform the whole binding check before arming the raw _guards ownership/mode pass."""
            nonlocal checked
            real_check(directories)
            if armed:
                checked = True

        def fstat(fd):
            """Fail only the ancestor's raw post-binding fstat, outside checkout error translation."""
            nonlocal reached
            info = real_fstat(fd)
            if checked and (info.st_dev, info.st_ino) == (ancestor.st_dev, ancestor.st_ino):
                reached = True
                raise OSError(errno.EIO, "injected raw final fstat")
            return info

        with patch("research_pipeline.vault._fault", side_effect=seam), \
             patch.object(_Directories, "check", check), \
             patch("research_pipeline.vault.os.fstat", side_effect=fstat), \
             self.assertRaises(ViewOperationalError) as caught:
            self.inspect()
        self.assertTrue(reached, "raw final ancestor fstat was not reached")
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assert_errno_cause(caught.exception, errno.EIO)


class PublicationPrimitiveTests(unittest.TestCase):
    """Exercise the real Linux no-replace primitive independently of external materialization fixtures."""

    def test_kernel_visibility_and_existing_directory_refusal(self):
        """A real same-parent rename preserves a protected tree and refuses an empty competitor intact."""
        from research_pipeline.vault import _rename_noreplace

        with TemporaryDirectory(prefix="no-replace-") as temporary:
            parent = Path(temporary)
            generation = parent / (".readable-generation-" + "a" * 32)
            generation.mkdir(mode=0o700)
            nested = generation / "nested"
            nested.mkdir(mode=0o700)
            (nested / "complete").write_bytes(b"complete")
            (nested / "complete").chmod(0o400)
            nested.chmod(0o500)
            generation.chmod(0o500)
            identities = {relative: (generation / relative).stat().st_ino
                          for relative in ("", "nested", "nested/complete")}
            parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                publish = _rename_noreplace()
                (parent / "destination").mkdir(mode=0o700)
                before = (parent / "destination").stat()
                with self.assertRaises(FileExistsError):
                    publish(parent_fd, generation.name, parent_fd, "destination")
                self.assertEqual((parent / "destination").stat(), before)
                self.assertEqual(list((parent / "destination").iterdir()), [])
                self.assertEqual((generation / "nested/complete").read_bytes(), b"complete")
                for relative, inode in identities.items():
                    info = (generation / relative).stat()
                    self.assertEqual(info.st_ino, inode)
                    self.assertEqual(stat.S_IMODE(info.st_mode), 0o400 if relative.endswith("complete") else 0o500)
                (parent / "destination").rmdir()
                publish(parent_fd, generation.name, parent_fd, "destination")
                self.assertFalse(generation.exists())
                self.assertEqual((parent / "destination/nested/complete").read_bytes(), b"complete")
                for relative, inode in identities.items():
                    info = (parent / "destination" / relative).stat()
                    self.assertEqual(info.st_ino, inode)
                    self.assertEqual(stat.S_IMODE(info.st_mode), 0o400 if relative.endswith("complete") else 0o500)
            finally:
                os.close(parent_fd)
                restore_directories(parent)

    def test_portable_siblings_and_incremental_parent_bound(self):
        """NFKC/case aliases and nonportable parents fail closed, and enumeration stops at its allowance."""
        from research_pipeline.vault import _absent

        with TemporaryDirectory(prefix="view-alias-") as temporary:
            parent = Path(temporary)
            fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                alias = parent / "Ｒｅａｄｉｎｇ"
                alias.write_bytes(b"unrelated")
                with self.assertRaises(ViewLayoutError):
                    _absent(fd, "reading", 10)
                self.assertEqual(alias.read_bytes(), b"unrelated")
                alias.unlink()
                (parent / "CON").write_bytes(b"unsafe portable sibling")
                with self.assertRaises(ViewLayoutError):
                    _absent(fd, "reading", 10)
                (parent / "CON").unlink()
                for name in ("first", "second"):
                    (parent / name).write_bytes(b"unrelated")
                with self.assertRaises(SnapshotLimitError):
                    _absent(fd, "reading", 1)
            finally:
                os.close(fd)
