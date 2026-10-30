"""Real-filesystem tests of local artifact ownership, integrity and publication failures."""

import errno
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_pipeline.artifacts import (
    ArtifactIOError, ArtifactIntegrityError, ArtifactLayoutError, ArtifactNotFoundError, ArtifactStore,
)
from research_pipeline.domain import ArtifactReference, DomainValidationError


class ArtifactTests(unittest.TestCase):
    """Exercise real bytes and narrow syscall failures without replacing filesystem storage."""

    def setUp(self):
        """Create a fresh private runtime area outside source for each test."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "artifacts"
        self.store = ArtifactStore.create(self.root)

    def object_path(self, reference):
        """Locate test-owned canonical files solely for deliberate corruption fixtures."""
        return self.root / "objects" / reference.digest

    def corrupt(self, path, data):
        """Simulate owner mutation and restore read-only mode inside this disposable fixture."""
        path.chmod(0o600)
        path.write_bytes(data)
        path.chmod(0o400)

    def assert_rejected_object(self, reference, data):
        """Require read, verify and reuse to reject the same unsafe canonical object."""
        with self.assertRaises(ArtifactIntegrityError):
            self.store.read(reference)
        with self.assertRaises(ArtifactIntegrityError):
            self.store.verify(reference)
        with self.assertRaises(ArtifactIntegrityError):
            self.store.put(data)

    def test_put_read_verify_reopen_and_stable_reuse(self):
        """Store empty/binary bytes, preserve reused inodes and distinguish changed content."""
        for data in (b"", b"\x00\xff\x80graph\n", b"connected"):
            with self.subTest(data=data):
                reference = self.store.put(data)
                self.assertEqual(reference, ArtifactReference(hashlib.sha256(data).hexdigest(), len(data)))
                path = self.object_path(reference)
                inode = path.stat().st_ino
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o400)
                self.assertEqual(path.stat().st_uid, os.geteuid())
                self.assertEqual(self.store.read(reference), data)
                self.assertIsNone(self.store.verify(reference))
                reopened = ArtifactStore.open(self.root)
                self.assertEqual(reopened.put(data), reference)
                self.assertEqual(reopened.read(reference), data)
                self.assertEqual(path.stat().st_ino, inode)
                self.assertNotEqual(self.store.put(data + b"changed"), reference)
        for path in (self.root, self.root / "objects", self.root / ".staging"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
            self.assertEqual(path.stat().st_uid, os.geteuid())
        self.assertEqual(list((self.root / ".staging").iterdir()), [])

    def test_create_open_separation_and_non_destructive_refusal(self):
        """Existing roots and incomplete areas are never replaced, repaired or chmodded."""
        missing = self.parent / "missing"
        with self.assertRaises(ArtifactLayoutError):
            ArtifactStore.open(missing)
        self.assertFalse(missing.exists())
        with self.assertRaises(ArtifactLayoutError):
            ArtifactStore.create(missing / "child")
        self.assertFalse(missing.exists())
        sentinel = self.root / "keep"
        sentinel.write_bytes(b"untouched")
        with self.assertRaises(ArtifactLayoutError):
            ArtifactStore.create(self.root)
        self.assertEqual(sentinel.read_bytes(), b"untouched")
        (self.root / ".staging").rmdir()
        with self.assertRaises(ArtifactLayoutError):
            ArtifactStore.open(self.root)
        self.assertFalse((self.root / ".staging").exists())
        ordinary = self.parent / "file"
        ordinary.write_bytes(b"file")
        for operation in (ArtifactStore.create, ArtifactStore.open):
            with self.assertRaises(ArtifactLayoutError):
                operation(ordinary)
        self.assertEqual(ordinary.read_bytes(), b"file")

    def test_layout_privacy_and_ownership_rechecked_during_operations(self):
        """Reject weakened permissions or ownership after construction without repairing them."""
        reference = self.store.put(b"data")
        for directory in (self.root, self.root / "objects", self.root / ".staging"):
            with self.subTest(directory=directory.name):
                directory.chmod(0o750)
                try:
                    for operation in (lambda: ArtifactStore.open(self.root),
                                      lambda: self.store.put(b"data"),
                                      lambda: self.store.read(reference),
                                      lambda: self.store.verify(reference)):
                        with self.assertRaises(ArtifactLayoutError):
                            operation()
                    self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o750)
                finally:
                    directory.chmod(0o700)
        effective_uid = os.geteuid()
        with patch("research_pipeline.artifacts.os.geteuid", return_value=effective_uid + 1):
            with self.assertRaises(ArtifactLayoutError):
                ArtifactStore.open(self.root)

    def test_directory_symlinks_and_outside_sentinel(self):
        """Reject symlinked roots, ancestors and managed directories without outside effects."""
        outside = self.parent / "outside"
        outside.mkdir(mode=0o700)
        sentinel = outside / "keep"
        sentinel.write_bytes(b"outside")
        link = self.parent / "linked"
        link.symlink_to(outside, target_is_directory=True)
        for path in (link, link / "new", link / ".." / "new"):
            for operation in (ArtifactStore.create, ArtifactStore.open):
                with self.subTest(path=path), self.assertRaises(ArtifactLayoutError):
                    operation(path)
        for name in ("objects", ".staging"):
            path = self.root / name
            path.rmdir()
            path.symlink_to(outside, target_is_directory=True)
            try:
                with self.assertRaises(ArtifactLayoutError):
                    ArtifactStore.open(self.root)
                with self.assertRaises(ArtifactLayoutError):
                    self.store.put(b"new")
            finally:
                path.unlink()
                path.mkdir(mode=0o700)
        self.assertEqual(sentinel.read_bytes(), b"outside")
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ["keep"])
        self.assertFalse((self.parent / "new").exists())

    def test_missing_wrong_size_and_corrupt_objects(self):
        """Detect missing bytes, false sizes, same-size mutation and truncation on all paths."""
        data = b"original"
        reference = self.store.put(data)
        path = self.object_path(reference)
        for operation in (self.store.read, self.store.verify):
            with self.assertRaises(ArtifactIntegrityError):
                operation(ArtifactReference(reference.digest, len(data) + 1))
        for changed in (b"mutated!", b"short"):
            self.corrupt(path, changed)
            before = (path.read_bytes(), path.stat().st_ino, path.stat().st_mode)
            self.assert_rejected_object(reference, data)
            self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mode), before)
        path.unlink()
        for operation in (self.store.read, self.store.verify):
            with self.assertRaisesRegex(ArtifactNotFoundError, reference.digest):
                operation(reference)
        self.assertFalse(path.exists())

    def test_unsafe_canonical_objects(self):
        """Reject writable files, directories, live/dangling symlinks and FIFOs without hangs."""
        data = b"object"
        reference = self.store.put(data)
        path = self.object_path(reference)
        path.chmod(0o600)
        self.assert_rejected_object(reference, data)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        path.unlink()
        outside = self.parent / "sentinel"
        outside.write_bytes(data)
        for target in (outside, self.parent / "absent"):
            path.symlink_to(target)
            self.assert_rejected_object(reference, data)
            self.assertTrue(path.is_symlink())
            path.unlink()
        self.assertEqual(outside.read_bytes(), data)
        path.mkdir()
        self.assert_rejected_object(reference, data)
        path.rmdir()
        os.mkfifo(path, 0o400)
        self.assert_rejected_object(reference, data)
        self.assertTrue(stat.S_ISFIFO(path.lstat().st_mode))

    def test_fifo_replacement_between_inspection_and_open_is_nonblocking(self):
        """A raced FIFO cannot block open before descriptor type validation rejects it."""
        reference = self.store.put(b"data")
        path = self.object_path(reference)
        real_open = os.open
        replaced = False

        def replace_before_open(name, flags, *args, **kwargs):
            """Replace the inspected regular file with a real FIFO at the open boundary."""
            nonlocal replaced
            if name == reference.digest and not replaced:
                replaced = True
                self.assertTrue(flags & os.O_NONBLOCK)
                path.unlink()
                os.mkfifo(path, 0o400)
            return real_open(name, flags, *args, **kwargs)

        with patch("research_pipeline.artifacts.os.open", side_effect=replace_before_open):
            with self.assertRaises(ArtifactIntegrityError):
                self.store.read(reference)
        self.assertTrue(replaced)

    def test_input_types_and_forged_path_like_references(self):
        """Reject mutable inputs and malformed typed addresses before accessing object names."""
        for value in ("filename", bytearray(b"x"), memoryview(b"x"), None, 1):
            with self.subTest(value=type(value).__name__), self.assertRaises(DomainValidationError):
                self.store.put(value)
        sentinel = self.parent / "sentinel"
        sentinel.write_bytes(b"keep")
        forged = ArtifactReference("a" * 64, 4)
        object.__setattr__(forged, "digest", "../../sentinel")
        for value in (forged, {"digest": "a" * 64, "size": 0}, "../sentinel"):
            for operation in (self.store.read, self.store.verify):
                with self.assertRaises(DomainValidationError):
                    operation(value)
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.assertEqual(list((self.root / "objects").iterdir()), [])

    def test_failure_before_link_has_no_partial_canonical_object(self):
        """A failed publication link preserves its cause and removes only its own staging entry."""
        retained = self.root / ".staging" / "older-interruption"
        retained.write_bytes(b"retained")
        error = OSError(errno.EIO, "injected link failure")
        with patch("research_pipeline.artifacts.os.link", side_effect=error):
            with self.assertRaises(ArtifactIOError) as caught:
                self.store.put(b"new bytes")
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(list((self.root / "objects").iterdir()), [])
        self.assertEqual(list((self.root / ".staging").iterdir()), [retained])
        self.assertEqual(retained.read_bytes(), b"retained")

    def test_partial_writes_and_operational_read_failure(self):
        """Complete short real writes and expose read errors with their underlying cause."""
        real_write = os.write

        def short_write(descriptor, data):
            """Write only a small prefix to force repeated actual filesystem writes."""
            return real_write(descriptor, data[:3])

        data = b"several short writes preserve all bytes"
        with patch("research_pipeline.artifacts.os.write", side_effect=short_write):
            reference = self.store.put(data)
        self.assertEqual(self.store.read(reference), data)
        error = OSError(errno.EIO, "injected read error")
        with patch("research_pipeline.artifacts.os.read", side_effect=error):
            for operation in (self.store.read, self.store.verify):
                with self.assertRaises(ArtifactIOError) as caught:
                    operation(reference)
                self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(self.store.read(reference), data)

    def test_opened_object_ownership_is_checked(self):
        """A foreign-owned descriptor fails even after safe path inspection and opening."""
        reference = self.store.put(b"owned bytes")
        real_fstat = os.fstat

        def foreign_file(descriptor):
            """Simulate foreign inode ownership only for the real opened regular file."""
            info = real_fstat(descriptor)
            if stat.S_ISREG(info.st_mode):
                fields = list(info)
                fields[4] = os.geteuid() + 1
                return os.stat_result(fields)
            return info

        with patch("research_pipeline.artifacts.os.fstat", side_effect=foreign_file):
            self.assert_rejected_object(reference, b"owned bytes")
        self.assertEqual(self.store.read(reference), b"owned bytes")

    def test_file_sync_failure_does_not_publish(self):
        """Fail the inode durability barrier before any canonical link can be created."""
        real_fsync = os.fsync

        def fail_file_sync(descriptor):
            """Inject a real-file synchronization failure while allowing directory cleanup."""
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError(errno.EIO, "file fsync failed")
            real_fsync(descriptor)

        with patch("research_pipeline.artifacts.os.fsync", side_effect=fail_file_sync):
            with self.assertRaises(ArtifactIOError):
                self.store.put(b"not durable")
        self.assertEqual(list((self.root / "objects").iterdir()), [])
        self.assertEqual(list((self.root / ".staging").iterdir()), [])

    def test_post_link_directory_sync_failure_retains_object(self):
        """Failed directory durability acknowledgment never reports success or rolls back bytes."""
        data = b"published before failure"
        reference = ArtifactReference(hashlib.sha256(data).hexdigest(), len(data))
        real_fsync = os.fsync
        objects_inode = (self.root / "objects").stat().st_ino

        def fail_objects_sync(descriptor):
            """Fail only the actual objects directory barrier after the real hard link."""
            if os.fstat(descriptor).st_ino == objects_inode:
                raise OSError(errno.EIO, "objects fsync failed")
            real_fsync(descriptor)

        with patch("research_pipeline.artifacts.os.fsync", side_effect=fail_objects_sync):
            with self.assertRaises(ArtifactIOError):
                self.store.put(data)
        self.assertEqual(self.object_path(reference).read_bytes(), data)
        self.assertEqual(list((self.root / ".staging").iterdir()), [])
        self.assertEqual(ArtifactStore.open(self.root).put(data), reference)

    def test_cleanup_failure_preserves_original_diagnostic(self):
        """Best-effort staging removal cannot hide the original failed link operation."""
        original = OSError(errno.EXDEV, "hard links unavailable")
        with patch("research_pipeline.artifacts.os.link", side_effect=original), \
                patch("research_pipeline.artifacts.os.unlink", side_effect=OSError(errno.EIO, "cleanup failed")):
            with self.assertRaises(ArtifactIOError) as caught:
                self.store.put(b"failure")
        self.assertIs(caught.exception.__cause__, original)
        self.assertEqual(list((self.root / "objects").iterdir()), [])
        self.assertEqual(len(list((self.root / ".staging").iterdir())), 1)

    def test_concurrent_winner_is_verified_without_clobber(self):
        """Two opened publishers use real no-clobber links and verify the winning inode."""
        for corrupt_winner in (False, True):
            with self.subTest(corrupt_winner=corrupt_winner):
                data = b"race-good" if not corrupt_winner else b"race-bad"
                reference = ArtifactReference(hashlib.sha256(data).hexdigest(), len(data))
                other = ArtifactStore.open(self.root)
                real_link = os.link
                winner_inode = None
                racing = False

                def publish_winner(source, destination, **kwargs):
                    """Publish through a second real store immediately before the first link."""
                    nonlocal racing, winner_inode
                    if not racing:
                        racing = True
                        other.put(data)
                        winner_inode = self.object_path(reference).stat().st_ino
                        if corrupt_winner:
                            self.corrupt(self.object_path(reference), b"x" * len(data))
                    return real_link(source, destination, **kwargs)

                with patch("research_pipeline.artifacts.os.link", side_effect=publish_winner):
                    if corrupt_winner:
                        with self.assertRaises(ArtifactIntegrityError):
                            self.store.put(data)
                    else:
                        self.assertEqual(self.store.put(data), reference)
                path = self.object_path(reference)
                self.assertEqual(path.stat().st_ino, winner_inode)
                self.assertEqual(path.read_bytes(), b"x" * len(data) if corrupt_winner else data)
                self.assertEqual(list((self.root / ".staging").iterdir()), [])

    def test_success_follows_file_and_directory_syncs_including_reuse(self):
        """Observe actual sync order around real publication and verified reuse."""
        events = []
        real_fsync, real_link = os.fsync, os.link
        objects_inode = (self.root / "objects").stat().st_ino
        staging_inode = (self.root / ".staging").stat().st_ino

        def observe_sync(descriptor):
            """Record and perform each inode barrier, identifying owned directory inodes."""
            info = os.fstat(descriptor)
            name = {objects_inode: "objects", staging_inode: "staging"}.get(info.st_ino, "file")
            events.append(name)
            real_fsync(descriptor)

        def observe_link(*args, **kwargs):
            """Record the real no-overwrite publication boundary."""
            events.append("link")
            return real_link(*args, **kwargs)

        with patch("research_pipeline.artifacts.os.fsync", side_effect=observe_sync), \
                patch("research_pipeline.artifacts.os.link", side_effect=observe_link):
            reference = self.store.put(b"sync order")
            self.assertEqual(events, ["file", "link", "staging", "objects"])
            events.clear()
            self.assertEqual(self.store.put(b"sync order"), reference)
            self.assertEqual(events, ["file", "objects"])

    def test_create_synchronizes_layout_and_parent(self):
        """Creation acknowledgment follows barriers on children, root and its parent."""
        synchronized = []
        real_fsync = os.fsync

        def observe(descriptor):
            """Record actual directory inode barriers while retaining real durability calls."""
            synchronized.append(os.fstat(descriptor).st_ino)
            real_fsync(descriptor)

        root = self.parent / "second"
        with patch("research_pipeline.artifacts.os.fsync", side_effect=observe):
            ArtifactStore.create(root)
        self.assertEqual(synchronized, [(root / "objects").stat().st_ino,
                                        (root / ".staging").stat().st_ino,
                                        root.stat().st_ino, self.parent.stat().st_ino])

    def test_inert_imports_and_caller_relative_runtime_path(self):
        """Fresh source-local imports do no storage work; explicit relative roots use caller cwd."""
        source = Path(__file__).resolve().parents[1] / "src"
        program = '''
import os
import sys
from pathlib import Path
phase = "import"
def guard(event, arguments):
    """Forbid import-time mutations and network/process effects in the fresh interpreter."""
    if phase == "import":
        forbidden = event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn"))
        forbidden = forbidden or event in {"os.mkdir", "os.link", "os.chmod", "os.remove", "os.rename"}
        if event == "open":
            forbidden = forbidden or bool(arguments[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
        if forbidden:
            raise RuntimeError("import effect: " + event)
sys.addaudithook(guard)
from research_pipeline.domain import ArtifactReference
from research_pipeline.artifacts import ArtifactStore
phase = "runtime"
store = ArtifactStore.create("relative-runtime")
reference = store.put(b"caller relative")
assert store.read(reference) == b"caller relative"
assert Path("relative-runtime/objects", reference.digest).is_file()
'''
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=self.parent,
                                env={**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"},
                                capture_output=True, text=True, check=False, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((result.stdout, result.stderr), ("", ""))
