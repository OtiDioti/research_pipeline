"""Coordinated final-read mutations and strict interrupted-control validation regressions."""

import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
from dataclasses import replace
from unittest.mock import patch

from research_pipeline.snapshot import _canonical, SnapshotLimitError
from research_pipeline.view_capture import _identified
from research_pipeline.view_refresh import inspect_readable_refresh
from research_pipeline.view_plan import plan_readable_snapshot
from tests.view_refresh_fixtures import RefreshFixture, refresh_limits
from tests.view_capture_fixtures import SOURCE, tree_state
from tests.test_vault import child_environment
from tests.test_view_refresh_recovery import PUBLISHER
from tests.snapshot_fixtures import limits, selection
from tests.test_store import record, request
from tests.test_assessment_store import metadata


INSPECTOR = '''
import json, os, sys
import research_pipeline.view_refresh as refresh
from tests.view_refresh_fixtures import refresh_limits
original_stream, original_read = refresh._stream, os.read
active = None
paused = False
def stream(fd, reference, path):
    """Select only the concluding verification stream, never initial traversal reads."""
    global active
    active = fd if path == sys.argv[4] else None
    try:
        return original_stream(fd, reference, path)
    finally:
        active = None
def read(fd, size):
    """Pause after a real first chunk so a parent can edit already-hashed bytes."""
    global paused
    data = original_read(fd, size)
    if fd == active and data and not paused:
        paused = True
        print("chunk", flush=True)
        assert sys.stdin.readline().strip() == "continue"
    return data
refresh._stream = stream
os.read = read
result = refresh.inspect_readable_refresh(sys.argv[1], sys.argv[2], source_root=sys.argv[3],
    protected_roots=[], limits=refresh_limits())
print(json.dumps([result.status, result.verified_package_path, result.successor_path, result.preservation_path]), flush=True)
'''


WRITER = PUBLISHER.replace('refresh._fault = seam', '''
original_stream, original_read = refresh._stream, os.read
original_pins = refresh._check_pins
armed = paused = pins_finished = False
active = None
def arm(point):
    """Arm only after the published marker, before the writer's last verification."""
    global armed
    if point == "after_published":
        armed = True
    seam(point)
def pins(*args, **kwargs):
    """Record completion of the final preservation/control hashing section."""
    global pins_finished
    result = original_pins(*args, **kwargs)
    if armed:
        pins_finished = True
    return result
def stream(fd, reference, path):
    """Select a real writer read only in the armed final verification pass."""
    global active
    active = fd if armed and path == sys.argv[8] else None
    try:
        return original_stream(fd, reference, path)
    finally:
        active = None
def read(fd, size):
    """Pause after a real nonempty chunk and report which hashing section reached it."""
    global paused
    data = original_read(fd, size)
    if fd == active and data and not paused:
        paused = True
        print("chunk successor" if pins_finished else "chunk preservation", flush=True)
        assert sys.stdin.readline().strip() == "continue"
    return data
refresh._fault = arm
refresh._check_pins = pins
refresh._stream = stream
os.read = read
''').replace('print("ERROR " + str(error), flush=True)', '''import json
        print(json.dumps(dict(error=type(error).__name__, message=str(error),
            cause=type(error.__cause__).__name__, cause_message=str(error.__cause__))), flush=True)''')


class RefreshObservationTests(RefreshFixture):
    """Use real process coordination for final hashing and interrupted preparation boundaries."""

    def child(self, script, arguments):
        """Launch candidate-local Python and arrange deterministic cleanup of only this child."""
        child = subprocess.Popen([sys.executable, "-B", "-c", script, *map(str, arguments)],
            cwd=self.parent, env=child_environment(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop, child)
        return child

    def stop(self, child):
        """Reap a child even when a test assertion interrupts coordination."""
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)

    def reached(self, child, expected):
        """Require the actual pipe boundary within a deadline without using sleeps."""
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(30), "child boundary timeout")
        self.assertEqual(child.stdout.readline().strip(), expected)

    def test_mutations_during_final_hashing_are_inconsistent_and_read_only(self):
        """Already-read edits, earlier-file edits, replacement and directory mutations invalidate paths."""
        self.write("a-large.bin", b"a" * 200_000)
        self.write("z-later.bin", b"z" * 200_000)
        for kind in ("same_file", "earlier_file", "replacement", "membership", "rebind", "transient"):
            with self.subTest(kind=kind):
                result = self.refresh(destination=self.parent / kind)
                root = Path(result.destination)
                first = root / "preservation/tree/a-large.bin"
                target = "a-large.bin" if kind == "same_file" else "z-later.bin"
                child = self.child(INSPECTOR, [result.attempt_path, result.destination, SOURCE,
                    "package/preservation/tree/" + target])
                self.reached(child, "chunk")
                if kind in ("same_file", "earlier_file"):
                    with first.open("r+b") as stream:
                        stream.write(b"mutated!")
                elif kind == "replacement":
                    replacement = first.with_name("replacement.bin")
                    replacement.write_bytes(first.read_bytes())
                    replacement.chmod(0o600)
                    replacement.replace(first)
                elif kind == "rebind":
                    directory = first.parent
                    directory.rename(directory.with_name("moved-tree"))
                    directory.mkdir(mode=0o700)
                else:
                    added = first.parent / "new-entry"
                    added.write_bytes(b"new")
                    added.chmod(0o600)
                    if kind == "transient":
                        added.unlink()
                after_mutation = tree_state(root), tree_state(Path(result.attempt_path))
                output, error = child.communicate("continue\n", timeout=40)
                self.assertEqual(child.returncode, 0, error)
                self.assertEqual(json.loads(output), ["inconsistent", None, None, None])
                self.assertEqual((tree_state(root), tree_state(Path(result.attempt_path))), after_mutation)
                if kind in ("same_file", "earlier_file"):
                    self.assertTrue(first.read_bytes().startswith(b"mutated!"))

    def preparation(self, destination, boundary="controls"):
        """Interrupt after a real pinned file write, all controls, or successor construction."""
        manifest = self.parent / "pinned.json"
        manifest.write_bytes(self.plan.manifest_bytes)
        manifest.chmod(0o600)
        script = PUBLISHER.replace('refresh._fault = seam', '''
original_generation, original_pin = refresh._prepare_generation, refresh._write_pin
def before_generation(*args, **kwargs):
    """Offer an interruption after controls and before the first successor file."""
    seam("controls")
    return original_generation(*args, **kwargs)
def after_pin(stack, tree, path, data, mode):
    """Offer an interruption only after bytes are written, synced and pinned."""
    result = original_pin(stack, tree, path, data, mode)
    seam("written:" + path)
    return result
refresh._prepare_generation = before_generation
refresh._write_pin = after_pin
refresh._fault = seam''')
        child = self.child(script, [self.runtime, manifest, self.view, destination, SOURCE, boundary, "die"])
        output, error = child.communicate(timeout=40)
        self.assertEqual(child.returncode, 73, output + error)
        attempt = next(a for a in self.parent.glob(".readable-refresh-attempt-*")
                       if json.loads((a / "intent.json").read_bytes())["destination"] == destination.name)
        intent = json.loads((attempt / "intent.json").read_bytes())
        return attempt, self.parent / intent["package_name"]

    def inspect_partial(self, attempt, destination):
        """Inspect retained private evidence with no store/prior access or writes."""
        return inspect_readable_refresh(attempt, destination, source_root=SOURCE,
            protected_roots=[self.runtime], limits=refresh_limits())

    def assert_inconsistent(self, result):
        """Require corruption to clear every claimed identity and verified path."""
        self.assertEqual(result.status, "inconsistent", result.differences)
        self.assertEqual((result.refresh_id, result.verified_package_path,
                          result.successor_path, result.preservation_path), (None, None, None, None))

    def test_fixed_control_directories_are_not_unwritten_files(self):
        """Reject each fixed file substitution at interrupted stages, before descending into it."""
        controls = ("capture.json", "preservation-plan.json", "README.md", "refresh.json",
                    "preservation/controls/expected-manifest.json",
                    "preservation/controls/observed-manifest.bin", "generation/manifest.json")
        prior, canonical = tree_state(self.view), metadata(self.runtime)
        objects = tree_state(self.runtime / "objects")
        for index, relative in enumerate(controls):
            with self.subTest(relative=relative):
                destination = self.parent / f"control-directory-{index}"
                boundary = "after_successor" if relative == "generation/manifest.json" else "written:" + relative
                attempt, root = self.preparation(destination, boundary)
                path = root / relative
                self.assertTrue(path.is_file())
                self.assertFalse((attempt / "ready.json").exists())
                if relative == "capture.json":
                    for unwritten in ("preservation-plan.json", "README.md", "refresh.json"):
                        self.assertFalse((root / unwritten).exists())
                    self.assertEqual(list((root / "generation").iterdir()), [])
                before = tree_state(root), tree_state(attempt)
                result = self.inspect_partial(attempt, destination)
                self.assertEqual(result.status, "incomplete_preparation", result.differences)
                self.assertEqual((tree_state(root), tree_state(attempt)), before)
                # No descriptor or later dependency is needed to establish the
                # fixed file type, even at the earliest capture-only boundary.
                path.parent.chmod(0o700)
                path.unlink()
                path.mkdir(mode=0o700)
                for competing in (False, True):
                    if competing:
                        destination.mkdir(mode=0o700)
                    before = tree_state(root), tree_state(attempt), tree_state(destination)
                    result = self.inspect_partial(attempt, destination)
                    self.assert_inconsistent(result)
                    self.assertIn(relative, result.differences[0].detail)
                    self.assertEqual((tree_state(root), tree_state(attempt), tree_state(destination)), before)
                # A nonempty substitute is rejected at its own path. Its unsafe
                # descendant would raise a layout error if traversal reached it.
                (path / "uninterpreted-link").symlink_to("missing")
                before = tree_state(root), tree_state(attempt), tree_state(destination)
                result = self.inspect_partial(attempt, destination)
                self.assert_inconsistent(result)
                self.assertIn(relative, result.differences[0].detail)
                self.assertEqual((tree_state(root), tree_state(attempt), tree_state(destination)), before)
                self.assertEqual(tree_state(self.view), prior)
                self.assertEqual(metadata(self.runtime), canonical)
                self.assertEqual(tree_state(self.runtime / "objects"), objects)

    def test_writer_final_hashing_rechecks_published_directories(self):
        """Final preservation and successor reads detect real directory mutations and retain output."""
        self.write("large.bin", b"preserved bytes\n" * 20_000)
        prior, canonical = tree_state(self.view), metadata(self.runtime)
        objects = tree_state(self.runtime / "objects")
        manifest = self.parent / "writer-plan.json"
        manifest.write_bytes(self.plan.manifest_bytes)
        manifest.chmod(0o600)
        # Artifact paths cannot also name top-level controls in _check_pins.
        successor_file = self.plan.artifact_copies[0].relative_path
        for phase, target in (("preservation", "preservation/tree/large.bin"), ("successor", successor_file)):
            for mutation in ("rebind", "membership", "mode", "stable"):
                with self.subTest(phase=phase, mutation=mutation):
                    destination = self.parent / (phase + "-" + mutation)
                    child = self.child(WRITER, [self.runtime, manifest, self.view, destination, SOURCE,
                                               "unused", "wait", target])
                    self.reached(child, "chunk " + phase)
                    attempt = next(a for a in self.parent.glob(".readable-refresh-attempt-*")
                        if json.loads((a / "intent.json").read_bytes())["destination"] == destination.name)
                    intent = json.loads((attempt / "intent.json").read_bytes())
                    preparation = self.parent / intent["package_name"]
                    self.assertFalse(preparation.exists())
                    self.assertTrue((attempt / "published.json").is_file())
                    directory = destination / "preservation/tree"
                    if mutation == "rebind":
                        directory.rename(directory.with_name("moved-tree"))
                        directory.mkdir(mode=0o700)
                    elif mutation == "membership":
                        (directory / "added-directory").mkdir(mode=0o700)
                    elif mutation == "mode":
                        directory.chmod(0o500)
                    before = tree_state(destination), tree_state(attempt)
                    output, error = child.communicate("continue\n", timeout=40)
                    self.assertEqual(child.returncode, 0, error)
                    self.assertEqual((tree_state(destination), tree_state(attempt)), before)
                    self.assertEqual(tree_state(self.view), prior)
                    self.assertEqual(metadata(self.runtime), canonical)
                    self.assertEqual(tree_state(self.runtime / "objects"), objects)
                    inspected = self.inspect_partial(attempt, destination)
                    if mutation == "stable":
                        self.assertEqual(output.strip(), "SUCCESS " + str(attempt))
                        self.assertEqual(inspected.status, "published", inspected.differences)
                    else:
                        failure = json.loads(output)
                        self.assertEqual(failure["error"], "ViewOperationalError")
                        self.assertEqual(failure["cause"], "ViewIntegrityError")
                        self.assertTrue(failure["cause_message"])
                        self.assertIn("uncertain publication acknowledgment", failure["message"])
                        for path in (destination, attempt, preparation):
                            self.assertIn(str(path), failure["message"])
                        self.assert_inconsistent(inspected)
                    if mutation == "rebind":
                        self.assertEqual(list(directory.iterdir()), [])
                        self.assertEqual((directory.with_name("moved-tree") / "large.bin").read_bytes(),
                                         (self.view / "large.bin").read_bytes())
                    self.assertEqual((tree_state(destination), tree_state(attempt)), before)

    def test_present_controls_are_validated_without_requiring_future_files(self):
        """All legitimate unwritten control stages remain incomplete and never become verified."""
        destination = self.parent / "partial"
        attempt, root = self.preparation(destination)
        self.assertFalse((root / "generation/manifest.json").exists())
        for remove in (None, "refresh.json", "README.md", "preservation-plan.json", "capture.json"):
            if remove:
                (root / remove).unlink()
            before = tree_state(root), tree_state(attempt)
            result = self.inspect_partial(attempt, destination)
            self.assertEqual(result.status, "incomplete_preparation", result.differences)
            self.assertIsNone(result.successor_path)
            self.assertEqual((tree_state(root), tree_state(attempt)), before)

    def test_malformed_and_contradictory_partial_controls_are_inconsistent(self):
        """Canonical syntax, rehashed IDs and valid wrong-plan manifests cannot bypass schema/intent."""
        destination = self.parent / "tampered-partial"
        attempt, root = self.preparation(destination)
        for relative in ("capture.json", "preservation-plan.json", "refresh.json"):
            path = root / relative
            original = path.read_bytes()
            document = json.loads(original)
            identity_key = {"capture.json": "capture_id", "preservation-plan.json": "preservation_plan_id",
                            "refresh.json": "refresh_id"}[relative]
            contradictory = dict(document)
            if relative == "capture.json":
                contradictory["prior_view"] += "-different"
            elif relative == "preservation-plan.json":
                contradictory["capture_id"] = "0" * 64
            else:
                contradictory["prior"] = {**document["prior"], "plan_id": "0" * 64}
            contradictory[identity_key] = _identified(contradictory, identity_key)
            for value in ({}, {**document, "version": 2}, contradictory):
                with self.subTest(relative=relative, value=value.get("version")):
                    path.chmod(0o600)
                    path.write_bytes(_canonical(value).encode("ascii"))
                    path.chmod(0o400)
                    before = tree_state(root), tree_state(attempt)
                    result = self.inspect_partial(attempt, destination)
                    self.assertEqual(result.status, "inconsistent")
                    self.assertEqual((result.verified_package_path, result.successor_path, result.preservation_path),
                                     (None, None, None))
                    self.assertEqual((tree_state(root), tree_state(attempt)), before)
            path.chmod(0o600)
            path.write_bytes(original)
            path.chmod(0o400)
        # A plan without the earlier capture violates writer dependency order.
        (root / "capture.json").unlink()
        self.assertEqual(self.inspect_partial(attempt, destination).status, "inconsistent")

    def test_wrong_successor_manifest_and_independent_partial_capture_budget(self):
        """Partial inspection validates available plans and rejects nested capture excess before open."""
        destination = self.parent / "partial-budget"
        attempt, root = self.preparation(destination)
        chosen = refresh_limits()
        size = (root / "capture.json").stat().st_size
        chosen = replace(chosen, capture_limits=replace(chosen.capture_limits, max_metadata_bytes=size - 1))
        from research_pipeline.view_refresh_inspection import _inspect_open
        def open_control(stack, parent, name, info, path):
            """Fail if the oversized partial capture reaches the open boundary."""
            self.assertNotEqual(path, "package/capture.json")
            return _inspect_open(stack, parent, name, info, path)
        with patch("research_pipeline.view_refresh_inspection._inspect_open", open_control):
            with self.assertRaises(SnapshotLimitError):
                inspect_readable_refresh(attempt, destination, source_root=SOURCE,
                    protected_roots=[self.runtime], limits=chosen)
        self.store.submit(request("advance", [record("project", 2, "project")], {"project": 1}))
        wrong = plan_readable_snapshot(self.store.capture_snapshot(selection(), limits=limits()))
        manifest = root / "generation/manifest.json"
        manifest.write_bytes(wrong.manifest_bytes)
        manifest.chmod(0o400)
        before = tree_state(root), tree_state(attempt)
        self.assertEqual(self.inspect_partial(attempt, destination).status, "inconsistent")
        self.assertEqual((tree_state(root), tree_state(attempt)), before)
