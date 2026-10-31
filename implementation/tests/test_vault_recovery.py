"""Observable publication, interruption and mutation evidence without sleeps or automatic replay."""

import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
from unittest.mock import patch

from research_pipeline.store import RecordStore
from research_pipeline.vault import ViewError, ViewOperationalError
from tests.test_assessment_store import metadata
from tests.test_store import record, request
from tests.test_vault import VaultFixture, SOURCE, child_environment, paired_payload


PUBLISHER = '''
import json,os,sys
from pathlib import Path
import research_pipeline.vault as vault
from research_pipeline.store import RecordStore
from research_pipeline.view_plan import readable_plan_from_manifest
from tests.snapshot_fixtures import limits
plan = readable_plan_from_manifest(Path(sys.argv[2]).read_bytes(), limits=limits())

def seam(point):
    """Expose a real lifecycle boundary through a pipe, then await explicit release or terminate."""
    if point == sys.argv[5]:
        print(point, flush=True)
        if sys.argv[6] == "die":
            os._exit(73)
        assert sys.stdin.readline().strip() == "continue"
vault._fault = seam
with RecordStore.open(sys.argv[1]) as store:
    try:
        result = vault.materialize_readable_view(store, plan, sys.argv[3], source_root=sys.argv[4],
                                               protected_roots=[], max_entries=4096)
    except vault.ViewError as error:
        print("ERROR " + str(error), flush=True)
    else:
        print("SUCCESS " + result.attempt_path, flush=True)
'''


class RecoveryTests(VaultFixture):
    """Independent processes exercise the no-replace boundary and honestly retained acknowledgment evidence."""

    def save_manifest(self):
        """Save detached canonical plan bytes for a separately opened child process."""
        path = self.parent / "plan.json"
        path.write_bytes(self.plan.manifest_bytes)
        path.chmod(0o600)
        return path

    def publisher(self, point, destination=None, action="wait"):
        """Start one bounded pipe-controlled publisher with its own thread-confined store handle."""
        child = subprocess.Popen([sys.executable, "-B", "-c", PUBLISHER, str(self.root),
                                  str(self.save_manifest()), str(destination or self.destination),
                                  str(SOURCE), point, action], cwd=self.parent, env=child_environment(),
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop_child, child)
        return child

    def stop_child(self, child):
        """Reap only this disposable child, killing on failure rather than leaving a blocked subprocess."""
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)

    def reached(self, child, expected):
        """Wait with a deadline for a flushed lifecycle event, never using sleeps as coordination."""
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(30), "publisher did not reach lifecycle seam")
        actual = child.stdout.readline().strip()
        self.assertEqual(actual, expected)

    def release(self, child):
        """Release a parked process and require bounded clean process completion."""
        output, error = child.communicate("continue\n", timeout=30)
        self.assertEqual(child.returncode, 0, error)
        return output

    def test_two_independent_publishers_exactly_one_wins(self):
        """Both competitors reach rename; one wins and the other's protected sibling remains inspectable."""
        before = metadata(self.root)
        children = [self.publisher("at_rename") for _ in range(2)]
        for child in children:
            self.reached(child, "at_rename")
        for child in children:
            child.stdin.write("continue\n")
            child.stdin.flush()
        outputs = []
        for child in children:
            output, error = child.communicate(timeout=30)
            self.assertEqual(child.returncode, 0, error)
            outputs.append(output)
        self.assertEqual(sum("SUCCESS " in output for output in outputs), 1)
        self.assertEqual(sum("ERROR " in output for output in outputs), 1)
        self.assertEqual(self.inspect().status, "verified")
        attempts = list(self.parent.glob(".readable-view-*"))
        self.assertEqual(len(attempts), 2)
        self.assertEqual(sum((p / "published.json").exists() for p in attempts), 1)
        payloads = [paired_payload(p) for p in attempts if paired_payload(p).exists()]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(self.inspect(payloads[0]).status, "verified")
        for attempt in attempts:
            self.assertEqual({p.name for p in attempt.iterdir()},
                             {"intent.json", "ready.json", "published.json"}
                             if (attempt / "published.json").exists() else {"intent.json", "ready.json"})
        self.assertEqual(metadata(self.root), before)

    def test_external_file_directory_and_symlink_win_at_actual_rename(self):
        """A separate process creates a destination after absence checks and survives no-replace refusal intact."""
        for kind in ("directory", "file", "symlink"):
            destination = self.parent / kind
            child = self.publisher("at_rename", destination)
            self.reached(child, "at_rename")
            self.child('''
import os,sys
from pathlib import Path
path = Path(sys.argv[1])
if sys.argv[2] == "directory":
    path.mkdir(mode=0o700)
elif sys.argv[2] == "file":
    path.write_bytes(b"competitor")
    path.chmod(0o600)
else:
    path.symlink_to("absent-competitor")
''', destination, kind)
            before = destination.lstat()
            self.assertIn("ERROR ", self.release(child))
            self.assertEqual(destination.lstat(), before)
            if kind == "file":
                self.assertEqual(destination.read_bytes(), b"competitor")
            elif kind == "directory":
                self.assertEqual(list(destination.iterdir()), [])
            else:
                self.assertEqual(os.readlink(destination), "absent-competitor")

    def test_fresh_reader_on_both_sides_of_atomic_visibility(self):
        """Readers see a complete 0500/0400 tree at both rename boundaries, before acknowledgment."""
        for point in ("at_rename", "after_rename"):
            destination = self.parent / point
            child = self.publisher(point, destination)
            self.reached(child, point)
            self.child('''
import json,stat,sys
from pathlib import Path
from research_pipeline.vault import inspect_readable_view
from tests.snapshot_fixtures import limits
destination = Path(sys.argv[1])
attempt = next(p for p in destination.parent.glob(".readable-view-*")
               if json.loads((p / "intent.json").read_bytes())["destination"] == destination.name)
intent = json.loads((attempt / "intent.json").read_bytes())
assert intent["generation_name"] == ".readable-generation-" + intent["token"]
assert not (attempt / "published.json").exists()
if sys.argv[2] == "at_rename":
    assert not destination.exists()
    root = destination.parent / intent["generation_name"]
else:
    root = destination
    assert not (destination.parent / intent["generation_name"]).exists()
assert [root.stat().st_dev, root.stat().st_ino] == intent["generation"]
assert inspect_readable_view(root, limits=limits(), max_entries=4096,
                             expected_plan_id=intent["plan_id"]).status == "verified"
manifest = json.loads((root / "manifest.json").read_bytes())
expected = {d["path"] for d in manifest["directories"]} | {f["path"] for f in manifest["files"]} | {"manifest.json"}
assert {""} | {str(p.relative_to(root)) for p in root.rglob("*")} == expected
for entry in manifest["directories"]:
    assert stat.S_IMODE((root / entry["path"]).stat().st_mode) == 0o500
for name in [f["path"] for f in manifest["files"]] + ["manifest.json"]:
    assert stat.S_IMODE((root / name).stat().st_mode) == 0o400
''', destination, point)
            self.assertIn("SUCCESS ", self.release(child))

    def test_termination_evidence_at_all_lifecycle_boundaries(self):
        """Abrupt exits retain token-paired reservation, incomplete, ready or uncertain publication evidence."""
        points = ("after_attempt_reservation", "after_generation_reservation", "after_intent", "after_file", "after_ready",
                  "before_rename", "at_rename", "after_rename", "after_publication_sync", "after_published")
        prior = set()
        before = metadata(self.root)
        for point in points:
            destination = self.parent / point
            child = self.publisher(point, destination, "die")
            output, error = child.communicate(timeout=30)
            self.assertEqual(child.returncode, 73, error)
            self.assertEqual(output.strip(), point)
            attempts = set(self.parent.glob(".readable-view-*"))
            fresh = attempts - prior
            self.assertEqual(len(fresh), 1)
            attempt = fresh.pop()
            prior = attempts
            after = point in ("after_rename", "after_publication_sync", "after_published")
            self.assertEqual(destination.exists(), after)
            no_intent = point in ("after_attempt_reservation", "after_generation_reservation")
            self.assertEqual((attempt / "intent.json").exists(), not no_intent)
            self.assertEqual((attempt / "ready.json").exists(),
                             not no_intent and point not in ("after_intent", "after_file"))
            self.assertEqual((attempt / "published.json").exists(), point == "after_published")
            payload = paired_payload(attempt)
            self.assertEqual(payload.exists(), not after and point != "after_attempt_reservation")
            self.assertTrue({p.name for p in attempt.iterdir()} <= {"intent.json", "ready.json", "published.json"})
            if no_intent:
                self.assertEqual(list(attempt.iterdir()), [])
                if payload.exists():
                    self.assertEqual(list(payload.iterdir()), [])
                    self.assertEqual(payload.stat().st_mode & 0o777, 0o700)
            if after:
                intent = json.loads((attempt / "intent.json").read_bytes())
                self.assertEqual(intent["generation"], [destination.stat().st_dev, destination.stat().st_ino])
                self.assertEqual(self.inspect(destination).status, "verified")
            self.assertEqual(metadata(self.root), before)

    def test_live_head_advances_before_and_during_preparation(self):
        """A detached plan retains revision one even as independent live commits advance its project twice."""
        self.store.submit(request("advance-before", [record("project", 2, "project")], {"project": 1}))
        child = self.publisher("after_intent")
        self.reached(child, "after_intent")
        with RecordStore.open(self.root) as writer:
            writer.submit(request("advance-during", [record("project", 3, "project")], {"project": 2}))
        self.assertIn("SUCCESS ", self.release(child))
        descriptor = json.loads((self.destination / "manifest.json").read_bytes())
        self.assertEqual(descriptor["resolutions"], [{"record_id": "project", "revision": 1}])
        self.assertEqual(descriptor["plan_id"], self.plan.plan_id)
        self.assertEqual(self.store.head("project"), 3)

    def test_fsync_rename_and_acknowledgment_failures(self):
        """Every barrier failure retains output; post-rename failures explicitly retain uncertainty."""
        real_sync = os.fsync
        for point in ("after_intent", "after_ready", "after_rename", "after_publication_sync"):
            destination = self.parent / point
            armed = False

            def seam(boundary):
                """Arm one real synchronization failure only after the requested completed operation."""
                nonlocal armed
                if boundary == point:
                    armed = True

            def synchronize(fd):
                """Fail the next real file/directory barrier without altering files or cleanup semantics."""
                if armed:
                    raise OSError("injected fsync failure")
                return real_sync(fd)

            with patch("research_pipeline.vault._fault", side_effect=seam), \
                 patch("research_pipeline.vault.os.fsync", side_effect=synchronize), \
                 self.assertRaises(ViewOperationalError) as caught:
                self.publish(destination)
            self.assertIn("attempt_path", str(caught.exception))
            if point in ("after_ready", "after_rename", "after_publication_sync"):
                self.assertTrue(destination.exists())
                self.assertIn("uncertain publication acknowledgment", str(caught.exception))
                self.assertEqual(self.inspect(destination).status, "verified")
            else:
                self.assertFalse(destination.exists())
        def unsupported(*args):
            """Simulate one refused kernel publication without any overwriting fallback."""
            raise OSError("unsupported")

        with patch("research_pipeline.vault._rename_noreplace", return_value=unsupported), \
             self.assertRaises(ViewOperationalError):
            self.publish()
        self.assertFalse(self.destination.exists())

    def test_close_failure_after_publication_is_uncertain(self):
        """Descriptor close failure cannot convert an exposed complete generation into reported rollback."""
        real_close = os.close
        armed = False

        def seam(point):
            """Arm close failure only once the real publication evidence has been synchronized."""
            nonlocal armed
            if point == "after_published":
                armed = True

        def close(fd):
            """Close the real resource, then simulate a lost successful-close acknowledgment once."""
            nonlocal armed
            real_close(fd)
            if armed:
                armed = False
                raise OSError("injected close acknowledgment failure")

        with patch("research_pipeline.vault._fault", side_effect=seam), \
             patch("research_pipeline.vault.os.close", side_effect=close), \
             self.assertRaisesRegex(ViewOperationalError, "uncertain publication acknowledgment"):
            self.publish()
        self.assertEqual(self.inspect().status, "verified")

    def test_parent_and_generation_replacement_fail_closed(self):
        """A moved parent or replaced preparation binding never succeeds at another pathname."""
        parent = self.parent / "destination-parent"
        parent.mkdir(mode=0o700)

        def seam(point):
            """Replace the held destination parent after durable intent to exercise ancestor checks."""
            if point == "after_intent":
                parent.rename(self.parent / "moved-parent")
                parent.mkdir(mode=0o700)

        with patch("research_pipeline.vault._fault", side_effect=seam), self.assertRaises(ViewError):
            self.publish(parent / "reading")
        self.assertEqual(list(parent.iterdir()), [])
        self.assertFalse((self.parent / "moved-parent/reading").exists())

        def replace_payload(point):
            """Substitute the 0500 sibling root before publication while retaining its original inode."""
            if point == "before_rename":
                attempt = next(self.parent.glob(".readable-view-*"))
                payload = paired_payload(attempt)
                payload.rename(self.parent / "moved-payload")
                payload.mkdir(mode=0o700)
                (payload / "sentinel").write_bytes(b"replacement")

        with patch("research_pipeline.vault._fault", side_effect=replace_payload), self.assertRaises(ViewError):
            self.publish()
        self.assertFalse(self.destination.exists())
        attempt = next(self.parent.glob(".readable-view-*"))
        self.assertEqual((paired_payload(attempt) / "sentinel").read_bytes(), b"replacement")
        self.assertEqual(self.inspect(self.parent / "moved-payload").status, "verified")

    def test_output_replacement_and_hardlink_fail_before_publication(self):
        """A retained sibling payload's output cannot be replaced or shared before final verification."""
        for kind in ("replace", "hardlink"):
            changed = False

            def seam(point):
                """Alter the first completed output by a separate binding before the read-back gate."""
                nonlocal changed
                if point == "after_file" and not changed:
                    changed = True
                    attempt = next(p for p in self.parent.glob(".readable-view-*")
                                   if (paired_payload(p) / "README.md").exists() and not (p / "ready.json").exists())
                    leaf = paired_payload(attempt) / "README.md"
                    if kind == "replace":
                        data = leaf.read_bytes()
                        leaf.unlink()
                        leaf.write_bytes(data)
                        leaf.chmod(0o400)
                    else:
                        os.link(leaf, self.parent / "foreign-link")

            with patch("research_pipeline.vault._fault", side_effect=seam), self.assertRaises(ViewError):
                self.publish(self.parent / kind)
            self.assertFalse((self.parent / kind).exists())
            # Retain attempts, but remove the known test-owned first README to distinguish the next seam.
            for attempt in self.parent.glob(".readable-view-*"):
                generation = paired_payload(attempt)
                generation.chmod(0o700)
                (generation / "README.md").unlink(missing_ok=True)

    def test_source_replacement_and_growth_while_streaming(self):
        """The copied stream and final source bindings reject substitution or mutation without repairing it."""
        original_path = self.root / "objects" / self.artifact.digest
        real_read = os.read
        changed = False

        def read(fd, size):
            """Grow the canonical inode immediately after its first actual bounded source read."""
            nonlocal changed
            info = os.fstat(fd)
            data = real_read(fd, size)
            self.assertLessEqual(size, 65536)
            if not changed and info.st_ino == original_path.stat().st_ino and data:
                changed = True
                original_path.chmod(0o600)
                with original_path.open("ab") as writer:
                    writer.write(b"growth")
                original_path.chmod(0o400)
            return data

        with patch("research_pipeline.vault.os.read", side_effect=read), self.assertRaises(ViewError):
            self.publish()
        self.assertTrue(changed)
        self.assertFalse(self.destination.exists())
        self.assertTrue(original_path.read_bytes().endswith(b"growth"))

    def test_source_binding_substitution_after_ready(self):
        """Even an identical replacement source inode after copying fails the final source-binding gate."""
        source = self.root / "objects" / self.artifact.digest
        expected = source.read_bytes()
        before = metadata(self.root)

        def seam(point):
            """Replace the canonical name with identical bytes while the original inode remains pinned."""
            if point == "after_ready":
                source.rename(self.root / ".staging" / "observed-original")
                source.write_bytes(expected)
                source.chmod(0o400)

        with patch("research_pipeline.vault._fault", side_effect=seam), self.assertRaises(ViewError):
            self.publish()
        self.assertFalse(self.destination.exists())
        self.assertEqual(source.read_bytes(), expected)
        self.assertEqual(metadata(self.root), before)
        self.assertNotEqual(source.stat().st_ino, (self.root / ".staging/observed-original").stat().st_ino)

    def test_attempt_collision_and_unsupported_libc_retain_evidence(self):
        """Evidence collisions never adopt state; unsupported libc retains separate intent and payload."""
        occupied = self.parent / (".readable-view-" + "a" * 32)
        occupied.mkdir(mode=0o700)
        (occupied / "sentinel").write_bytes(b"unrelated")
        with patch("research_pipeline.vault.secrets.token_hex", return_value="a" * 32), self.assertRaises(ViewError):
            self.publish()
        self.assertEqual({p.name for p in occupied.iterdir()}, {"sentinel"})
        self.assertEqual((occupied / "sentinel").read_bytes(), b"unrelated")
        with patch("research_pipeline.vault._rename_noreplace", side_effect=ViewOperationalError("libc unsupported")), \
             self.assertRaises(ViewOperationalError):
            self.publish()
        attempt = next(p for p in self.parent.glob(".readable-view-*") if p != occupied)
        self.assertEqual({p.name for p in attempt.iterdir()}, {"intent.json"})
        self.assertEqual(list(paired_payload(attempt).iterdir()), [])
        self.assertFalse(self.destination.exists())

    def test_payload_collision_and_reserved_aliases_preserved(self):
        """Occupied or aliased payload names and aliases among proposed names fail without adoption."""
        token = "c" * 32
        payload_name = ".readable-generation-" + token
        attempt_name = ".readable-view-" + token
        for name in (payload_name, payload_name.upper(), attempt_name.upper()):
            occupied = self.parent / name
            occupied.mkdir(mode=0o700)
            (occupied / "sentinel").write_bytes(b"unrelated")
            before = occupied.stat()
            with patch("research_pipeline.vault.secrets.token_hex", return_value=token), self.assertRaises(ViewError):
                self.publish()
            self.assertEqual(occupied.stat(), before)
            self.assertEqual({p.name for p in occupied.iterdir()}, {"sentinel"})
            self.assertEqual((occupied / "sentinel").read_bytes(), b"unrelated")
            (occupied / "sentinel").unlink()
            occupied.rmdir()
        for name in (attempt_name, attempt_name.upper(), payload_name, payload_name.upper()):
            with patch("research_pipeline.vault.secrets.token_hex", return_value=token), self.assertRaises(ViewError):
                self.publish(self.parent / name)
            self.assertFalse((self.parent / name).exists())
        self.assertFalse(list(self.parent.glob(".readable-view-*")))
        self.assertFalse(list(self.parent.glob(".readable-generation-*")))

    def test_payload_occupation_between_reservations_retains_evidence(self):
        """An intervening payload reservation is preserved and the empty evidence directory remains diagnostic."""
        token = "d" * 32
        payload = self.parent / (".readable-generation-" + token)

        def seam(point):
            """Occupy the paired name after evidence reservation but before payload creation."""
            if point == "after_attempt_reservation":
                payload.mkdir(mode=0o700)
                (payload / "sentinel").write_bytes(b"competitor")

        with patch("research_pipeline.vault.secrets.token_hex", return_value=token), \
             patch("research_pipeline.vault._fault", side_effect=seam), self.assertRaises(ViewError) as caught:
            self.publish()
        self.assertIn(str(payload), str(caught.exception))
        self.assertIn("attempt_path", str(caught.exception))
        self.assertEqual((payload / "sentinel").read_bytes(), b"competitor")
        self.assertEqual(list((self.parent / (".readable-view-" + token)).iterdir()), [])
        self.assertFalse(self.destination.exists())

    def test_parent_enumeration_bound_precedes_object_reads(self):
        """A crowded destination parent exceeds the explicit allowance before an attempt or source read."""
        maximum = len(self.plan.generated_files) + len(self.plan.artifact_copies) + len(self.plan.directories) - 1
        for index in range(maximum + 1):
            (self.parent / ("sibling-" + str(index))).write_bytes(b"unrelated")
        from research_pipeline.snapshot import SnapshotLimitError
        from research_pipeline.vault import materialize_readable_view
        with patch("research_pipeline.vault._stream", side_effect=AssertionError("must preflight parent")), \
             self.assertRaises(SnapshotLimitError):
            materialize_readable_view(self.store, self.plan, self.destination, source_root=SOURCE,
                                     protected_roots=[], max_entries=maximum)
        self.assertFalse(list(self.parent.glob(".readable-view-*")))
