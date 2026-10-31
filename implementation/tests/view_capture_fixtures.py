"""Private candidate-local fixtures for bounded capture and pure preservation tests."""

from dataclasses import replace
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.store import RecordStore
from research_pipeline.view_plan import plan_readable_snapshot
from research_pipeline.vault import materialize_readable_view
from research_pipeline.view_capture import CaptureLimits, capture_readable_view
from tests.snapshot_fixtures import limits, selection, populated
from tests.test_store import record, request
from tests.test_vault import restore_directories


SOURCE = Path(__file__).resolve().parents[1]


def capture_limits(**changes):
    """Return explicit generous independent budgets with precise boundary-test overrides."""
    value = CaptureLimits(limits(), 4096, 2048, 2048, 32, 10_000_000,
                          50_000_000, 50_000_000, 10000, 4096)
    return replace(value, **changes)


def tree_state(root):
    """Snapshot paths, bytes, modes and bindings without atime, excluding no human material."""
    result = {}
    for current, directories, files in os.walk(root, followlinks=False):
        for path in [Path(current), *(Path(current) / name for name in directories + files)]:
            info = path.lstat()
            data = path.read_bytes() if stat.S_ISREG(info.st_mode) else os.readlink(path) if path.is_symlink() else None
            result[str(path.relative_to(root))] = (info.st_dev, info.st_ino, info.st_mode,
                                                   info.st_uid, info.st_gid, info.st_nlink, data)
    return result


class CaptureFixture(unittest.TestCase):
    """Shared disposable setup only; subclasses never inherit test-bearing classes."""

    def setUp(self):
        """Publish a real canonical generation and retain its independent plan before local edits."""
        temporary = TemporaryDirectory(prefix="view-capture-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.parent.chmod(0o700)
        self.addCleanup(restore_directories, self.parent)
        self.runtime = self.parent / "runtime"
        self.store = RecordStore.create(self.runtime)
        self.addCleanup(self.store.close)
        self.artifact = self.store.put_artifact(b"duplicate synthetic original\n")
        self.store.submit(request("project", [record("project", kind="project",
            artifact_references=[self.artifact, self.artifact])]))
        self.plan = plan_readable_snapshot(self.store.capture_snapshot(selection(), limits=limits()))
        self.view = self.parent / "reading"
        self.publish()

    def publish(self):
        """Materialize exact synthetic bytes outside executing implementation/runtime boundaries."""
        materialize_readable_view(self.store, self.plan, self.view,
            source_root=SOURCE, protected_roots=[], max_entries=4096)

    def capture(self, **options):
        """Capture against independent plan and explicit runtime exclusion, with optional budgets."""
        arguments = dict(expected_plan=self.plan, source_root=SOURCE,
                         protected_roots=[self.runtime], limits=capture_limits())
        arguments.update(options)
        return capture_readable_view(self.view, **arguments)

    def write(self, relative, data, mode=0o600):
        """Simulate an owner's explicit inert edit/addition with private paths and exact permissions."""
        path = self.view / relative
        path.parent.chmod(0o700)
        if path.exists():
            path.chmod(0o600)
        path.write_bytes(data)
        path.chmod(mode)
        return path

    def rename(self, relative, target):
        """Simulate a human rename without losing bytes or silently repairing any other path."""
        path, destination = self.view / relative, self.view / target
        path.parent.chmod(0o700)
        destination.parent.chmod(0o700)
        path.rename(destination)

    def populated_view(self):
        """Build the accepted rich dossier fixture in a second independent store/generation."""
        self.store.close()
        # The reused source-capture fixture excludes the entire repository, so
        # its supplied inputs require the controller's writable external /tmp.
        temporary = TemporaryDirectory(prefix="rich-view-capture-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.addCleanup(restore_directories, self.parent)
        self.runtime = self.parent / "rich-runtime"
        self.store = RecordStore.create(self.runtime)
        self.addCleanup(self.store.close)
        chosen, payloads = populated(self.store, self.parent)
        self.plan = plan_readable_snapshot(self.store.capture_snapshot(chosen, limits=limits()))
        self.view = self.parent / "rich-reading"
        self.publish()
        return payloads
