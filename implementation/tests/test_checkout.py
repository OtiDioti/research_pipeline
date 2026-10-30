"""Real bounded checkout publication, substitution, interruption and inert-content tests."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import checkout
from research_pipeline.checkout import (
    CheckoutError, CheckoutInfo, CheckoutIntegrityError, CheckoutLayoutError,
    CheckoutOperationalError, checkout_work_product, inspect_checkout,
)
from research_pipeline.domain import DomainValidationError, RecordEnvelope, RecordReference
from research_pipeline.store import RecordNotFoundError, RecordStore, StoreClosedError
from research_pipeline.work_product import WorkProductFile, encode_envelope
from tests.test_assessment_store import metadata
from tests.test_store import CREATOR, record, request
from tests.test_work_product import manifest


class CheckoutTests(unittest.TestCase):
    """Use private disposable source/exclusion trees and actual stores; never touch source files."""

    def setUp(self):
        """Create committed text/binary/repeated/empty files and explicit trusted exclusion roots."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.source_tree = self.parent / "software"
        self.source_tree.mkdir()
        self.protected = self.parent / "external-controls"
        self.protected.mkdir()
        self.destination = self.parent / "draft"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)
        self.text = "Synthetic note α\n".encode()
        self.binary = b"\x00\xff\x80"
        self.a = self.store.put_artifact(self.text)
        self.b = self.store.put_artifact(self.binary)
        self.empty = self.store.put_artifact(b"")
        self.value = replace(manifest(self.a), files=[
            WorkProductFile("notes/α.txt", self.a), WorkProductFile("data/raw.bin", self.b),
            WorkProductFile("copy.txt", self.a), WorkProductFile("empty", self.empty)])
        self.envelope = encode_envelope("bundle", 1, self.value, CREATOR)
        self.store.submit_typed(request(records=[self.envelope]))
        self.base = RecordReference("bundle", 1, "checkout_base", "work_product_manifest")
        self.options = dict(source_root=self.source_tree, protected_roots=[self.protected],
                            max_file_bytes=1024 * 1024, max_total_bytes=4 * 1024 * 1024,
                            max_files=20, max_descriptor_bytes=100_000)

    def run_checkout(self, destination=None, **options):
        """Invoke the public API with explicit limits and caller-owned exclusion fixtures."""
        return checkout_work_product(self.store, self.base, destination or self.destination,
                                     **{**self.options, **options})

    def snapshot(self, exclude=()):
        """Snapshot every application table and safe object bytes/types without opening special files."""
        objects = {}
        for path in (self.root / "objects").iterdir():
            if path.name in exclude:
                continue
            info = path.lstat()
            content = path.read_bytes() if stat.S_ISREG(info.st_mode) else None
            objects[path.name] = (info.st_mode, info.st_uid, info.st_size, content)
        return metadata(self.root), objects

    def rejected(self, operation, error=CheckoutError, *, incomplete=True, exclude=()):
        """Require useful failure, unchanged unaffected canonical data and retained publication state."""
        before = self.snapshot(exclude)
        with self.assertRaises(error) as caught:
            operation()
        self.assertTrue(str(caught.exception))
        self.assertEqual(self.snapshot(exclude), before)
        if incomplete:
            self.assertTrue(self.destination.is_dir())
            self.assertTrue((self.destination / ".work-product/incomplete").exists())
            with self.assertRaises(CheckoutError):
                inspect_checkout(self.destination, max_descriptor_bytes=100_000)
        return caught.exception

    def child(self, program, *arguments, expected=0):
        """Run fresh candidate-source Python with finite deadlines and no bytecode writes."""
        source = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run([sys.executable, "-B", "-c", program, *map(str, arguments)],
                                cwd=self.parent, env={**os.environ, "PYTHONPATH": str(source),
                                                     "PYTHONDONTWRITEBYTECODE": "1"},
                                text=True, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout

    def rewrite(self, path, data, mode=0o400):
        """Deliberately simulate an owner changing one disposable file and restoring its mode."""
        path.chmod(0o600)
        path.write_bytes(data)
        path.chmod(mode)

    def test_independent_history_descriptor_and_fresh_inspection(self):
        """Old revisions retain exact attribution, inventory and independent writable copies after head advance."""
        second = encode_envelope("bundle", 2, replace(self.value, title="new title"), CREATOR)
        self.store.submit_typed(request("append", [second], {"bundle": 1}))
        before = self.snapshot()
        info = self.run_checkout()
        self.assertEqual(info, CheckoutInfo(self.base, self.envelope))
        self.assertIsNot(info.envelope, self.envelope)
        self.assertIsNot(info.envelope.provenance, self.envelope.provenance)
        with self.assertRaises(FrozenInstanceError):
            info.base = self.base
        data = info.envelope.content
        data["files"].clear()
        self.assertEqual(info.envelope, self.envelope)
        descriptor = self.destination / ".work-product/checkout.json"
        expected = dict(format="research_pipeline.work_product_checkout", version=1,
                        base=self.base.to_dict(), envelope=self.envelope.to_dict())
        self.assertEqual(descriptor.read_bytes(), json.dumps(expected, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=True).encode())
        identities = set()
        for entry in self.value.files:
            path = self.destination / entry.path
            self.assertEqual(path.read_bytes(), self.store.read_artifact(entry.artifact))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(path.stat().st_nlink, 1)
            self.assertNotEqual(path.stat().st_ino, (self.root / "objects" / entry.artifact.digest).stat().st_ino)
            identities.add((path.stat().st_dev, path.stat().st_ino))
        self.assertEqual(len(identities), 4)
        self.assertEqual(stat.S_IMODE(descriptor.stat().st_mode), 0o400)
        (self.destination / self.value.entry_file).write_bytes(b"edited")
        (self.destination / "extra").write_bytes(b"unselected")
        (self.destination / "empty").unlink()
        self.assertEqual((self.destination / "copy.txt").read_bytes(), self.text)
        self.assertEqual(inspect_checkout(self.destination, max_descriptor_bytes=100_000), info)
        self.assertEqual(self.snapshot(), before)
        self.store._artifacts.verify(self.a)
        output = self.child('''
import json, sys
from research_pipeline.checkout import inspect_checkout
from research_pipeline.store import RecordStore
info = inspect_checkout(sys.argv[1], max_descriptor_bytes=100000)
with RecordStore.open(sys.argv[2]) as store:
    assert store.head("bundle") == 2
    assert info.envelope == store.get_typed_revision("bundle", 1)[0]
print(json.dumps(info.envelope.to_dict(), sort_keys=True))
''', self.destination, self.root)
        self.assertEqual(json.loads(output), self.envelope.to_dict())

    def test_exact_budgets_and_preflight_rejection(self):
        """All four budgets count logical copies; invalid budgets reserve nothing and read no objects."""
        descriptor_size = len(checkout._encode(CheckoutInfo(self.base, self.envelope)))
        exact = dict(max_file_bytes=len(self.text), max_total_bytes=2 * len(self.text) + len(self.binary),
                     max_files=4, max_descriptor_bytes=descriptor_size)
        before = self.snapshot()
        for name in exact:
            with self.subTest(name=name):
                with patch.object(checkout, "_leaf", side_effect=AssertionError("preflight opened a file")):
                    self.rejected(lambda: self.run_checkout(**{**exact, name: exact[name] - 1}),
                                  DomainValidationError, incomplete=False)
                self.assertFalse(self.destination.exists())
        for name in self.options.keys() - {"source_root", "protected_roots"}:
            for bad in (True, False, -1, None, float("inf"), 1.0, "1"):
                with self.subTest(name=name, bad=bad):
                    self.rejected(lambda: self.run_checkout(**{name: bad}),
                                  DomainValidationError, incomplete=False)
                    self.assertFalse(self.destination.exists())
        for name in ("max_files", "max_descriptor_bytes"):
            self.rejected(lambda: self.run_checkout(**{name: 0}), DomainValidationError, incomplete=False)
        self.run_checkout(**exact)
        self.assertEqual(inspect_checkout(self.destination, max_descriptor_bytes=descriptor_size).base, self.base)
        self.assertEqual(self.snapshot(), before)

    def test_empty_files_allow_zero_byte_budgets(self):
        """Zero-byte materialization succeeds with exact zero per-file/aggregate bounds."""
        value = replace(self.value, files=[WorkProductFile("empty", self.empty)], entry_file="empty")
        self.store.submit_typed(request("zero", [encode_envelope("zero", 1, value, CREATOR)]))
        self.base = replace(self.base, record_id="zero")
        self.run_checkout(max_file_bytes=0, max_total_bytes=0, max_files=1)
        self.assertEqual((self.destination / "empty").read_bytes(), b"")

    def test_invalid_base_and_generic_envelopes_never_reserve(self):
        """Exact roles, forged fields, missing/closed stores and malformed committed content retain meaning."""
        for field, value in (("relationship", "other"), ("target_kind", "claim"),
                             ("revision", True), ("record_id", "../bad")):
            bad = replace(self.base)
            object.__setattr__(bad, field, value)
            self.rejected(lambda: checkout_work_product(self.store, bad, self.destination, **self.options),
                          DomainValidationError, incomplete=False)
        missing = replace(self.base, revision=99)
        self.rejected(lambda: checkout_work_product(self.store, missing, self.destination, **self.options),
                      RecordNotFoundError, incomplete=False)
        documents = [record("wrong", kind="source"), record("generic", kind="work_product_manifest"),
                     RecordEnvelope("future", 1, "work_product_manifest",
                                    {**self.envelope.content, "version": 2}, CREATOR),
                     RecordEnvelope("incoherent", 1, "work_product_manifest", self.envelope.content, CREATOR)]
        self.store.submit(request("generic", documents))
        for envelope in documents:
            self.rejected(lambda: checkout_work_product(self.store, replace(self.base, record_id=envelope.record_id),
                          self.destination, **self.options), DomainValidationError, incomplete=False)
        self.assertFalse(self.destination.exists())
        self.store.close()
        with self.assertRaises(StoreClosedError):
            self.run_checkout()

    def test_reserved_aliases_are_checkout_only_and_prefixes_remain_valid(self):
        """Reserved control aliases remain readable manifests but cannot collide with checkout controls."""
        for index, path in enumerate((".work-product", ".WORK-PRODUCT/a", ".ｗork-product/x")):
            value = replace(self.value, files=[WorkProductFile(path, self.a)], entry_file=path)
            identity = f"alias-{index}"
            envelope = encode_envelope(identity, 1, value, CREATOR)
            self.store.submit_typed(request(identity, [envelope]))
            self.assertEqual(self.store.get_typed_revision(identity, 1)[0], envelope)
            self.rejected(lambda: checkout_work_product(self.store, replace(self.base, record_id=identity),
                          self.destination, **self.options), DomainValidationError, incomplete=False)
        value = replace(self.value, files=[WorkProductFile(".work-product-other/a", self.a)],
                        entry_file=".work-product-other/a")
        self.store.submit_typed(request("prefix", [encode_envelope("prefix", 1, value, CREATOR)]))
        self.base = replace(self.base, record_id="prefix")
        self.run_checkout()
        self.assertEqual((self.destination / value.entry_file).read_bytes(), self.text)

    def test_existing_destinations_and_boundary_spellings(self):
        """Existing entries and overlapping roots are refused unchanged, including aliases and reverse containment."""
        sentinel = self.protected / "sentinel"
        sentinel.write_bytes(b"preserved")
        existing = [self.parent / name for name in ("file", "directory", "dangling")]
        existing[0].write_bytes(b"existing")
        existing[1].mkdir()
        existing[2].symlink_to(self.parent / "absent")
        roots = [self.source_tree, self.root, self.root / "objects", self.root / ".staging", self.protected]
        bad = existing + roots + [p / "nested" for p in roots] + [self.parent]
        bad += [str(self.parent) + "/x/../draft", "//" + str(self.root).lstrip("/") + "/draft"]
        bad += [os.path.relpath(self.source_tree / "draft", Path.cwd())]
        for destination in bad:
            with self.subTest(destination=destination):
                self.rejected(lambda: self.run_checkout(destination), incomplete=False)
        self.assertEqual(existing[0].read_bytes(), b"existing")
        self.assertEqual(list(existing[1].iterdir()), [])
        self.assertTrue(existing[2].is_symlink())
        self.assertEqual(sentinel.read_bytes(), b"preserved")
        self.rejected(lambda: self.run_checkout(protected_roots=None), DomainValidationError, incomplete=False)
        for invalid in (None, False, 1, "invalid\0path"):
            self.rejected(lambda: self.run_checkout(source_root=invalid), DomainValidationError, incomplete=False)

    def test_symlinked_missing_ancestors_and_recognizable_storage(self):
        """Ancestor traversal refuses symlinks, missing parents and omitted recognizable controls without reads."""
        link = self.parent / "link"
        link.symlink_to(self.protected, target_is_directory=True)
        for destination in (link / "draft", self.parent / "absent/child"):
            self.rejected(lambda: self.run_checkout(destination), incomplete=False)
        layouts = ({"objects", ".staging"}, {"metadata.sqlite3"}, {"snapshot.sqlite3"},
                   {".backup-incomplete"}, {".restore-incomplete"}, {".work-product"})
        for index, names in enumerate(layouts):
            root = self.parent / f"layout-{index}"
            root.mkdir()
            for name in names:
                (root / name).symlink_to(root / "absent")
            self.rejected(lambda: self.run_checkout(root / "draft", protected_roots=[]), incomplete=False)
            self.assertFalse((root / "draft").exists())
        self.assertFalse((self.protected / "draft").exists())

    def test_relative_and_double_slash_success(self):
        """Caller cwd anchors relative destinations and POSIX // normalizes without symlink resolution."""
        self.child('''
import sys
from research_pipeline.checkout import checkout_work_product, inspect_checkout
from research_pipeline.domain import RecordReference
from research_pipeline.store import RecordStore
with RecordStore.open("runtime") as store:
    for path in ("relative-draft", "//" + sys.argv[1].lstrip("/") + "/double-draft"):
        info = checkout_work_product(store, RecordReference("bundle", 1, "checkout_base", "work_product_manifest"),
            path, source_root="software", protected_roots=["external-controls"], max_file_bytes=1000,
            max_total_bytes=4000, max_files=4, max_descriptor_bytes=100000)
        assert inspect_checkout(path, max_descriptor_bytes=100000) == info
''', self.parent)

    def test_missing_damaged_and_unsafe_canonical_objects(self):
        """Missing/truncated/wrong-hash/writable/symlink/FIFO/directory objects never publish or block."""
        path = self.root / "objects" / self.a.digest
        for index, kind in enumerate(("missing", "truncated", "hash", "writable", "symlink", "fifo", "directory")):
            with self.subTest(kind=kind):
                if path.exists():
                    path.unlink()
                if kind in ("truncated", "hash", "writable"):
                    data = self.text[:-1] if kind == "truncated" else b"x" * len(self.text)
                    path.write_bytes(data)
                    path.chmod(0o600 if kind == "writable" else 0o400)
                elif kind == "symlink":
                    path.symlink_to(self.root / "objects" / self.b.digest)
                elif kind == "fifo":
                    os.mkfifo(path, 0o400)
                elif kind == "directory":
                    path.mkdir()
                self.destination = self.parent / f"bad-object-{index}"
                self.rejected(self.run_checkout)
                if kind == "directory":
                    path.rmdir()
                elif kind != "missing":
                    path.unlink()
        path.write_bytes(self.text)
        path.chmod(0o400)

    def test_device_and_raced_fifo_are_refused_before_consumption(self):
        """Real /dev/null metadata and a raced FIFO exercise nonregular refusal without privileged creation."""
        real_stat, real_open = checkout._stat, os.open
        object_path = self.root / "objects" / self.a.digest
        device = os.stat("/dev/null")
        opened = []

        def device_stat(parent, name):
            """Inject an existing device's stat only at the selected canonical leaf."""
            return device if name == self.a.digest else real_stat(parent, name)

        def observe_open(name, flags, *args, **kwargs):
            """Record leaf attempts so the device test proves refusal precedes open."""
            opened.append(name)
            return real_open(name, flags, *args, **kwargs)

        with patch.object(checkout, "_stat", side_effect=device_stat), patch.object(checkout.os, "open", side_effect=observe_open):
            self.rejected(self.run_checkout)
        self.assertNotIn(self.a.digest, opened)
        self.destination = self.parent / "raced-fifo"

        def swap_open(name, flags, *args, **kwargs):
            """Substitute a FIFO after lstat; O_NONBLOCK prevents hanging on this actual inode."""
            if name == self.a.digest:
                object_path.unlink()
                os.mkfifo(object_path, 0o400)
            return real_open(name, flags, *args, **kwargs)

        with patch.object(checkout.os, "open", side_effect=swap_open):
            self.rejected(self.run_checkout, exclude=(self.a.digest,))

    def test_source_inplace_changes_growth_and_read_failures(self):
        """Bounded capture detects in-place changes, growth, early EOF and actual source read errors."""
        original_read = os.read
        path = self.root / "objects" / self.a.digest
        for index, failure in enumerate(("change", "grow", "truncate", "read")):
            self.destination = self.parent / f"read-{index}"
            self.rewrite(path, self.text)
            identity = path.stat().st_ino
            fired = False
            calls = []

            def read(fd, count):
                """Mutate the selected actual source inode only after its first successful read."""
                nonlocal fired
                if os.fstat(fd).st_ino != identity:
                    return original_read(fd, count)
                calls.append(count)
                if failure == "read":
                    raise OSError("injected source read failure")
                if not fired:
                    fired = True
                    data = original_read(fd, min(count, 2))
                    changed = {"change": b"x" * len(self.text), "grow": self.text + b"!", "truncate": b"S"}[failure]
                    self.rewrite(path, changed)
                    return data
                return original_read(fd, count)

            with patch.object(checkout.os, "read", side_effect=read):
                error = self.rejected(self.run_checkout, exclude=(self.a.digest,))
            self.assertIn(str(path), str(error))
            self.assertTrue(all(count <= len(self.text) for count in calls))
        self.rewrite(path, self.text)

    def test_source_replacement_and_layout_rebinding(self):
        """Replacement after a real copy, including identical bytes, cannot rebind canonical capture."""
        for index, kind in enumerate(("object", "objects", "runtime", "staging")):
            self.destination = self.parent / f"source-swap-{index}"
            selected = self.root / "objects" / self.a.digest if kind == "object" else (
                self.root if kind == "runtime" else self.root / (".staging" if kind == "staging" else "objects"))
            parked = selected.with_name(selected.name + "-parked")
            fired = False

            def fault(boundary):
                """Rename a selected source binding only after the first real product file copy."""
                nonlocal fired
                if boundary == "file_copied" and not fired:
                    fired = True
                    selected.rename(parked)
                    if kind == "object":
                        selected.write_bytes(self.text)
                        selected.chmod(0o400)
                    else:
                        selected.mkdir(mode=0o700)

            before = metadata(self.root)
            with patch.object(checkout, "_fault", side_effect=fault), self.assertRaises(CheckoutError):
                self.run_checkout()
            self.assertTrue(fired)
            self.assertTrue((self.destination / ".work-product/incomplete").exists())
            if kind == "object":
                selected.unlink()
            else:
                selected.rmdir()
            parked.rename(selected)
            self.assertEqual(metadata(self.root), before)
            self.store._artifacts.verify(self.a)
            self.store._artifacts.verify(self.b)

    def test_destination_binding_and_inventory_substitutions(self):
        """Prepublication seams cannot bypass file/directory/root/ancestor/control identity checks."""
        before = self.snapshot()
        for index, kind in enumerate(("file", "file-mode", "file-link", "directory", "root", "ancestor",
                                      "control", "marker", "descriptor", "extra", "missing")):
            holder = self.parent / f"holder-{index}"
            holder.mkdir()
            self.destination = holder / "draft"
            parked = holder / "parked"

            def fault(boundary):
                """Alter one completed private entry before the final verification gate."""
                if boundary != "before_publication":
                    return
                root = self.destination
                if kind == "file":
                    leaf = root / self.value.entry_file
                    leaf.rename(parked)
                    leaf.write_bytes(self.text)
                    leaf.chmod(0o600)
                elif kind == "file-mode":
                    (root / "copy.txt").chmod(0o700)
                elif kind == "file-link":
                    os.link(root / "copy.txt", holder / "hard-link")
                elif kind in ("directory", "root", "control"):
                    leaf = {"directory": root / "notes", "root": root, "control": root / ".work-product"}[kind]
                    leaf.rename(parked)
                    leaf.mkdir(mode=0o700)
                elif kind == "ancestor":
                    holder.rename(self.parent / f"parked-holder-{index}")
                    holder.mkdir(mode=0o700)
                elif kind in ("marker", "descriptor"):
                    leaf = root / ".work-product" / ("incomplete" if kind == "marker" else "checkout.json")
                    leaf.rename(parked)
                    leaf.symlink_to(parked)
                elif kind == "extra":
                    (root / "extra").write_bytes(b"unexpected")
                else:
                    (root / "empty").unlink()

            with self.subTest(kind=kind), patch.object(checkout, "_fault", side_effect=fault):
                with self.assertRaises(CheckoutError):
                    self.run_checkout()
            self.assertEqual(self.snapshot(), before)
            with self.assertRaises(CheckoutError):
                inspect_checkout(self.destination, max_descriptor_bytes=100_000)
            # A renamed root/control retains the original incomplete material too.
            retained = (self.parent / f"parked-holder-{index}" / "draft" if kind == "ancestor" else
                        parked if kind == "root" else self.destination)
            marker = parked / "incomplete" if kind == "control" else retained / ".work-product/incomplete"
            self.assertTrue(marker.exists())

    def test_short_writes_partial_failure_and_zero_progress(self):
        """Short real writes drain completely; failure after real bytes and zero progress retain incompleteness."""
        real_write = os.write

        def short(fd, data):
            """Write a bounded nonzero prefix using the actual syscall."""
            return real_write(fd, data[:3])

        before = self.snapshot()
        with patch.object(checkout.os, "write", side_effect=short):
            self.run_checkout()
        self.assertEqual((self.destination / self.value.entry_file).read_bytes(), self.text)
        self.assertEqual(self.snapshot(), before)
        for index, zero in enumerate((False, True)):
            self.destination = self.parent / f"partial-{index}"
            calls = 0

            def fail(fd, data):
                """Fail only after a real partial product write, preserving visible evidence."""
                nonlocal calls
                calls += 1
                if calls == 1:
                    return real_write(fd, data[:2])
                if zero:
                    return 0
                raise OSError("injected partial write failure")

            with patch.object(checkout.os, "write", side_effect=fail):
                self.rejected(self.run_checkout, CheckoutOperationalError)
            self.assertEqual((self.destination / self.value.entry_file).read_bytes(), self.text[:2])

    def test_inode_selected_durability_failures(self):
        """Fail actual marker/file/nested/control/root/parent barriers with truthful publication states."""
        real_sync = os.fsync
        for index, target in enumerate(("marker", "file", "nested", "control", "root", "parent", "final")):
            self.destination = self.parent / f"sync-{index}"
            after_copy = False
            removed = False
            fired = False

            def fault(boundary):
                """Track real lifecycle progress so directory faults target completion barriers."""
                nonlocal after_copy, removed
                after_copy = after_copy or boundary == "before_publication"
                removed = removed or boundary == "after_publication"

            def sync(fd):
                """Compare fstat with actual named inodes; never fail an unrelated source descriptor."""
                nonlocal fired
                candidates = {"marker": self.destination / ".work-product/incomplete",
                              "file": self.destination / self.value.entry_file,
                              "nested": self.destination / "notes", "control": self.destination / ".work-product",
                              "root": self.destination, "parent": self.parent,
                              "final": self.destination / ".work-product"}
                path = candidates[target]
                ready = (removed if target == "final" else after_copy if target in ("nested", "control", "root", "parent") else True)
                if ready and path.exists() and (os.fstat(fd).st_dev, os.fstat(fd).st_ino) == (path.stat().st_dev, path.stat().st_ino):
                    fired = True
                    raise OSError(f"injected {target} sync failure")
                return real_sync(fd)

            before = self.snapshot()
            with self.subTest(target=target), patch.object(checkout, "_fault", side_effect=fault), patch.object(checkout.os, "fsync", side_effect=sync):
                if target == "final":
                    with self.assertRaisesRegex(CheckoutOperationalError, "marker removed; final synchronization/acknowledgment uncertain"):
                        self.run_checkout()
                else:
                    self.rejected(self.run_checkout, CheckoutOperationalError)
            self.assertTrue(fired)
            self.assertEqual(self.snapshot(), before)
            if target == "final":
                self.assertEqual(inspect_checkout(self.destination, max_descriptor_bytes=100_000).base, self.base)

    def test_marker_unlink_and_post_removal_fault(self):
        """Unlink failure leaves incomplete output, while post-removal failure explicitly reports uncertainty."""
        real_unlink = os.unlink

        def unlink(name, *args, **kwargs):
            """Fail only the selected control marker removal after genuine construction and barriers."""
            if name == "incomplete":
                raise OSError("injected unlink failure")
            return real_unlink(name, *args, **kwargs)

        with patch.object(checkout.os, "unlink", side_effect=unlink):
            error = self.rejected(self.run_checkout, CheckoutOperationalError)
        self.assertNotIn("acknowledgment uncertain", str(error))
        self.destination = self.parent / "post-removal"

        def fault(boundary):
            """Raise after actual unlink to model lost acknowledgment without recreating the marker."""
            if boundary == "after_publication":
                raise OSError("lost acknowledgment")

        before = self.snapshot()
        with patch.object(checkout, "_fault", side_effect=fault):
            with self.assertRaisesRegex(CheckoutOperationalError, "marker removed; final synchronization/acknowledgment uncertain"):
                self.run_checkout()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.destination / ".work-product/incomplete").exists())
        self.assertEqual(inspect_checkout(self.destination, max_descriptor_bytes=100_000).envelope, self.envelope)

    def test_real_crashes_and_earlier_interrupted_construction(self):
        """Fresh processes refuse early/prepublication crashes and observe post-removal publication without acknowledgment."""
        before = self.snapshot()
        program = '''
import os, sys
from research_pipeline import checkout
from research_pipeline.domain import RecordReference
from research_pipeline.store import RecordStore
boundary = sys.argv[3]
if boundary == "before_marker":
    original = os.mkdir
    def mkdir(name, *args, **kwargs):
        """Exit after exclusive controls creation but before marker construction."""
        original(name, *args, **kwargs)
        if name == ".work-product":
            os._exit(73)
    checkout.os.mkdir = mkdir
else:
    def fault(point):
        """Exit at a real durable lifecycle boundary in the child process."""
        if point == boundary:
            os._exit(73)
    checkout._fault = fault
with RecordStore.open(sys.argv[1]) as store:
    checkout.checkout_work_product(store, RecordReference("bundle", 1, "checkout_base", "work_product_manifest"),
        sys.argv[2], source_root="software", protected_roots=["external-controls"], max_file_bytes=1000,
        max_total_bytes=4000, max_files=4, max_descriptor_bytes=100000)
raise AssertionError("termination seam was not reached")
'''
        for boundary in ("before_marker", "after_marker", "before_publication", "after_publication"):
            destination = self.parent / boundary
            self.child(program, self.root, destination, boundary, expected=73)
            self.assertTrue(destination.is_dir())
            self.assertEqual(self.snapshot(), before)
            self.child('''
import sys
from research_pipeline.checkout import CheckoutError, inspect_checkout
from research_pipeline.store import RecordStore
published = sys.argv[3] == "after_publication"
try:
    info = inspect_checkout(sys.argv[2], max_descriptor_bytes=100000)
except CheckoutError:
    assert not published
else:
    assert published and info.base.record_id == "bundle"
with RecordStore.open(sys.argv[1]) as store:
    assert store.head("bundle") == 1
    for item in store.get_revision("bundle", 1).artifact_references:
        store.read_artifact(item)
''', self.root, destination, boundary)

    def test_inspection_strict_descriptor_documents(self):
        """Malformed/duplicate/unsupported/incoherent and omitted nested fields fail without writes."""
        self.run_checkout()
        path = self.destination / ".work-product/checkout.json"
        original = path.read_bytes()
        document = json.loads(original)
        invalid = [b"{", b"\xff", b'{"x":NaN}', original.replace(b'"version":1', b'"version":true'),
                   original.replace(b'"version":1', b'"version":2'),
                   original[:-1] + b',"version":1}', original.replace(b'"size":17', b'"size":17,"size":17')]
        # Explicitly duplicate a deeply nested field independently of fixture byte lengths.
        invalid[-1] = original.replace(b'"digest":', b'"size":0,"digest":', 1)
        for change in ("extra", "missing", "base", "kind", "provenance", "links", "reference", "unicode", "bool-size"):
            value = deepcopy(document)
            if change == "extra":
                value["authority"] = True
            elif change == "missing":
                del value["envelope"]["operational_status"]
            elif change == "base":
                value["base"]["revision"] = 2
            elif change == "kind":
                value["envelope"]["kind"] = "source"
            elif change == "provenance":
                del value["envelope"]["provenance"]["details"]
            elif change == "links":
                value["envelope"]["artifact_references"] = []
            elif change == "reference":
                del value["base"]["target_kind"]
            elif change == "unicode":
                value["envelope"]["content"]["title"] = "\ud800"
            else:
                value["envelope"]["content"]["files"][-1]["artifact"]["size"] = False
            invalid.append(json.dumps(value).encode())
        before = self.snapshot()
        for data in invalid:
            with self.subTest(data=data[:60]):
                self.rewrite(path, data)
                with self.assertRaises(CheckoutError):
                    inspect_checkout(self.destination, max_descriptor_bytes=100_000)
                self.assertEqual(path.read_bytes(), data)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o400)
        self.assertEqual(self.snapshot(), before)

    def test_oversized_and_growing_descriptor(self):
        """Inspection bounds stat and streamed growth, without allocating the declared excessive size."""
        self.run_checkout()
        path = self.destination / ".work-product/checkout.json"
        original = path.read_bytes()
        with self.assertRaises(CheckoutIntegrityError):
            inspect_checkout(self.destination, max_descriptor_bytes=len(original) - 1)
        real_read = os.read
        identity = path.stat().st_ino
        sizes = []
        fired = False

        def grow(fd, count):
            """Grow the selected descriptor after one real bounded read."""
            nonlocal fired
            if os.fstat(fd).st_ino == identity:
                sizes.append(count)
                if not fired:
                    fired = True
                    chunk = real_read(fd, min(count, 10))
                    self.rewrite(path, original + b" " * 2000)
                    return chunk
            return real_read(fd, count)

        with patch.object(checkout.os, "read", side_effect=grow), self.assertRaises(CheckoutIntegrityError):
            inspect_checkout(self.destination, max_descriptor_bytes=len(original))
        self.assertTrue(fired)
        self.assertLessEqual(sum(sizes), len(original) * 2 + 1)
        self.assertEqual(sizes[-1], 1)

    def test_unsafe_controls_and_incomplete_entry_types(self):
        """Missing/extra/unsafe controls and every marker type remain unusable without repair."""
        before = self.snapshot()
        for index, kind in enumerate(("marker", "dangling-marker", "directory-marker", "fifo-marker", "missing-descriptor",
                                      "descriptor-link", "descriptor-fifo", "descriptor-directory", "descriptor-mode",
                                      "control-link", "control-mode", "extra")):
            self.destination = self.parent / f"controls-{index}"
            self.run_checkout()
            control = self.destination / ".work-product"
            descriptor, marker = control / "checkout.json", control / "incomplete"
            if kind == "marker":
                marker.write_bytes(b"")
                marker.chmod(0o400)
            elif kind == "dangling-marker":
                marker.symlink_to(control / "absent")
            elif kind == "directory-marker":
                marker.mkdir()
            elif kind == "fifo-marker":
                os.mkfifo(marker)
            elif kind.startswith("descriptor-") or kind == "missing-descriptor":
                if kind == "descriptor-mode":
                    descriptor.chmod(0o600)
                else:
                    descriptor.unlink()
                    if kind == "descriptor-link":
                        descriptor.symlink_to(control / "absent")
                    elif kind == "descriptor-fifo":
                        os.mkfifo(descriptor, 0o400)
                    elif kind == "descriptor-directory":
                        descriptor.mkdir()
            elif kind == "control-link":
                parked = self.parent / f"control-{index}"
                control.rename(parked)
                control.symlink_to(parked, target_is_directory=True)
            elif kind == "control-mode":
                control.chmod(0o755)
            else:
                (control / "extra").write_bytes(b"unexpected")
            with self.subTest(kind=kind), self.assertRaises(CheckoutError):
                inspect_checkout(self.destination, max_descriptor_bytes=100_000)
        self.assertEqual(self.snapshot(), before)

    def test_inspection_detects_descriptor_and_ancestor_replacement(self):
        """Read-only inspection rejects same-byte descriptor replacement and ancestor rebinding during reads."""
        self.run_checkout()
        real_read = os.read
        descriptor = self.destination / ".work-product/checkout.json"
        original = descriptor.read_bytes()
        fired = False

        def swap(fd, count):
            """Replace the descriptor pathname after actual bytes were consumed from its old inode."""
            nonlocal fired
            data = real_read(fd, count)
            if not fired:
                fired = True
                descriptor.rename(descriptor.with_name("old"))
                descriptor.write_bytes(original)
                descriptor.chmod(0o400)
            return data

        with patch.object(checkout.os, "read", side_effect=swap), self.assertRaises(CheckoutError):
            inspect_checkout(self.destination, max_descriptor_bytes=100_000)
        descriptor.with_name("old").unlink()
        fired = False

        def move(fd, count):
            """Rename the held checkout root during inspection; never change canonical storage."""
            nonlocal fired
            data = real_read(fd, count)
            if not fired:
                fired = True
                self.destination.rename(self.parent / "moved-draft")
                self.destination.mkdir(mode=0o700)
            return data

        with patch.object(checkout.os, "read", side_effect=move), self.assertRaises(CheckoutError):
            inspect_checkout(self.destination, max_descriptor_bytes=100_000)

    def test_coherent_owner_rewriting_is_not_authenticated(self):
        """An owner can rewrite coherent attribution; inspection reports local claims without canonical authority."""
        self.run_checkout()
        path = self.destination / ".work-product/checkout.json"
        document = json.loads(path.read_bytes())
        document["envelope"]["content"]["title"] = "owner's different declaration"
        document["envelope"]["provenance"]["actor"] = "unverified-other-author"
        self.rewrite(path, json.dumps(document).encode())
        before = self.snapshot()
        info = inspect_checkout(self.destination, max_descriptor_bytes=100_000)
        self.assertEqual(info.envelope.content["title"], "owner's different declaration")
        self.assertNotEqual(info.envelope, self.store.get_revision("bundle", 1))
        self.assertEqual(self.snapshot(), before)

    def test_scripts_configuration_notebooks_and_dependencies_are_inert(self):
        """Every format stays byte-identical and missing descriptive dependency bytes are never opened."""
        sentinel = self.parent / "executed"
        command = f"from pathlib import Path; Path({str(sentinel)!r}).write_text('executed')"
        payloads = {"run.py": command.encode(), "settings.py": command.encode(),
                    "run.sh": f"#!/bin/sh\necho executed > '{sentinel}'\n".encode(),
                    "notebook.ipynb": json.dumps({"cells": [{"cell_type": "code", "source": [command]}]}).encode()}
        dependency = self.store.put_artifact(b"dependency must not be read")
        self.store.submit(request("dependency", [record("dependency", kind="source", artifact_references=[dependency])]))
        files = [WorkProductFile(path, self.store.put_artifact(data)) for path, data in payloads.items()]
        value = replace(self.value, files=files, entry_file="run.py",
                        build_dependencies=[RecordReference("dependency", 1, "build_dependency", "source")])
        self.store.submit_typed(request("inert", [encode_envelope("inert", 1, value, CREATOR)]))
        (self.root / "objects" / dependency.digest).unlink()
        self.base = replace(self.base, record_id="inert")
        before = self.snapshot()
        self.run_checkout()
        self.assertEqual({path: (self.destination / path).read_bytes() for path in payloads}, payloads)
        self.assertEqual({p.name for p in self.destination.iterdir()}, set(payloads) | {".work-product"})
        self.assertFalse(sentinel.exists())
        self.assertEqual(self.snapshot(), before)

    def test_import_has_no_filesystem_effects(self):
        """Fresh module import performs no filesystem writes, process launches or network operations."""
        self.child('''
import sys
from pathlib import Path
before = sorted(str(path) for path in Path.cwd().rglob("*"))
def guard(event, args):
    """Reject observed writes, process launches and connections during import."""
    if event == "open":
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (1 | 2 | 64 | 512 | 1024):
            raise AssertionError((event, args))
    if event in ("os.mkdir", "os.remove", "os.rename", "subprocess.Popen", "socket.connect"):
        raise AssertionError((event, args))
sys.addaudithook(guard)
import research_pipeline.checkout
assert sorted(str(path) for path in Path.cwd().rglob("*")) == before
''')

    def test_large_capture_uses_bounded_chunks_and_exact_eof_probe(self):
        """A multi-chunk binary object is streamed without whole-bundle reads or excessive EOF probes."""
        payload = bytes(range(256)) * 700
        reference = self.store.put_artifact(payload)
        value = replace(self.value, files=[WorkProductFile("deep/a/b/data.bin", reference)],
                        entry_file="deep/a/b/data.bin")
        self.store.submit_typed(request("large", [encode_envelope("large", 1, value, CREATOR)]))
        self.base = replace(self.base, record_id="large")
        identity = (self.root / "objects" / reference.digest).stat().st_ino
        real_read = os.read
        reads = []

        def observe(fd, count):
            """Record requested read lengths only for the real canonical object inode."""
            if os.fstat(fd).st_ino == identity:
                reads.append(count)
            return real_read(fd, count)

        before = self.snapshot()
        with patch.object(checkout.os, "read", side_effect=observe):
            self.run_checkout(max_file_bytes=len(payload), max_total_bytes=len(payload), max_files=1)
        self.assertEqual((self.destination / value.entry_file).read_bytes(), payload)
        self.assertGreater(len(reads), 2)
        self.assertEqual(reads[-1], 1)
        self.assertTrue(all(size <= 64 * 1024 for size in reads))
        self.assertEqual(sum(reads), len(payload) + 1)
        self.assertEqual(self.snapshot(), before)

    def test_durability_order_and_metadata_transaction_lifetime(self):
        """Actual syncs establish the marker before products, then bottom-up construction and final barriers."""
        real_sync, real_unlink = os.fsync, os.unlink
        events = []
        published = False

        def sync(fd):
            """Identify actual affected inodes and retain their successful barrier order."""
            info = os.fstat(fd)
            candidates = [self.destination / ".work-product/incomplete",
                          self.destination / ".work-product/checkout.json",
                          *(self.destination / entry.path for entry in self.value.files),
                          self.destination / "notes", self.destination / "data",
                          self.destination / ".work-product", self.destination, self.parent]
            for path in candidates:
                if path.exists() and (info.st_dev, info.st_ino) == (path.stat().st_dev, path.stat().st_ino):
                    events.append(path)
                    break
            return real_sync(fd)

        def fault(boundary):
            """Assert durable marker ordering and the closed read transaction at real copy seams."""
            if boundary == "after_marker":
                self.assertEqual(events, [self.destination / ".work-product/incomplete",
                                          self.destination / ".work-product", self.destination, self.parent])
                self.assertEqual(set(self.destination.iterdir()), {self.destination / ".work-product"})
                self.assertEqual({p.name for p in (self.destination / ".work-product").iterdir()}, {"incomplete"})
            if boundary in ("after_marker", "file_copied", "before_publication"):
                self.assertFalse(self.store._require_open().in_transaction)
                self.assertFalse(published)

        def unlink(name, *args, **kwargs):
            """Observe real publication only after the complete directory barrier sequence."""
            nonlocal published
            if name == "incomplete":
                self.assertEqual(events[-3:], [self.destination / ".work-product", self.destination, self.parent])
                self.assertLess(events.index(self.destination / "notes"), len(events) - 3)
                self.assertLess(events.index(self.destination / "data"), len(events) - 3)
                result = real_unlink(name, *args, **kwargs)
                published = True
                return result
            return real_unlink(name, *args, **kwargs)

        before = self.snapshot()
        with patch.object(checkout.os, "fsync", side_effect=sync), patch.object(checkout.os, "unlink", side_effect=unlink), patch.object(checkout, "_fault", side_effect=fault):
            self.run_checkout()
        self.assertTrue(published)
        self.assertEqual(events[-3:], [self.destination / ".work-product", self.destination, self.parent])
        self.assertEqual(self.snapshot(), before)

    def test_substitution_during_final_prepublication_barrier(self):
        """Replacing completed bytes during a directory barrier still fails before marker removal."""
        real_sync = os.fsync
        ready = False
        fired = False

        def fault(boundary):
            """Arm mutation only after real complete construction, before verification and directory syncs."""
            nonlocal ready
            ready = ready or boundary == "before_publication"

        def sync(fd):
            """Replace one copied leaf while synchronizing its actual parent directory."""
            nonlocal fired
            directory = self.destination / "notes"
            if ready and not fired and directory.exists() and os.fstat(fd).st_ino == directory.stat().st_ino:
                fired = True
                leaf = self.destination / self.value.entry_file
                leaf.rename(self.parent / "old-copy")
                leaf.write_bytes(self.text)
                leaf.chmod(0o600)
            return real_sync(fd)

        with patch.object(checkout.os, "fsync", side_effect=sync), patch.object(checkout, "_fault", side_effect=fault):
            self.rejected(self.run_checkout)
        self.assertTrue(fired)

    def test_postpublication_descriptor_close_failure_is_uncertain(self):
        """Even a close failure after successful final barriers cannot be reported as rollback."""
        real_close = os.close
        removed = False
        fired = False

        def fault(boundary):
            """Remember actual marker removal before faulting a retained directory descriptor's close."""
            nonlocal removed
            removed = removed or boundary == "after_publication"

        def close(fd):
            """Close the real control directory and then report an operational acknowledgment failure."""
            nonlocal fired
            control = self.destination / ".work-product"
            selected = removed and not fired and control.exists() and os.fstat(fd).st_ino == control.stat().st_ino
            real_close(fd)
            if selected:
                fired = True
                raise OSError("injected close failure")

        before = self.snapshot()
        with patch.object(checkout, "_fault", side_effect=fault), patch.object(checkout.os, "close", side_effect=close):
            with self.assertRaisesRegex(CheckoutOperationalError, "marker removed; final synchronization/acknowledgment uncertain"):
                self.run_checkout()
        self.assertTrue(fired)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(inspect_checkout(self.destination, max_descriptor_bytes=100_000).base, self.base)

    def test_documented_checkout_example(self):
        """Execute the actual checkout-only documentation block in fresh candidate-source Python."""
        document = Path(__file__).resolve().parents[2] / "docs/checkout.md"
        program = document.read_text().split("```python\n", 1)[1].split("```", 1)[0]
        self.child(program)
