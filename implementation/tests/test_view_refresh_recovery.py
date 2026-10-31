"""Real refresh interruption, competing publication and offline tamper evidence."""

import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
from unittest.mock import patch

from research_pipeline.vault import ViewIntegrityError, ViewLayoutError
from research_pipeline.view_refresh import inspect_readable_refresh
from tests.view_refresh_fixtures import RefreshFixture, refresh_limits
from tests.view_capture_fixtures import SOURCE, tree_state
from tests.test_vault import child_environment
from tests.test_assessment_store import metadata


PUBLISHER = '''
import os,sys
from pathlib import Path
import research_pipeline.view_refresh as refresh
import research_pipeline.vault as vault
from research_pipeline.store import RecordStore
from research_pipeline.view_plan import readable_plan_from_manifest
from tests.snapshot_fixtures import limits
from tests.view_refresh_fixtures import refresh_limits
plan = readable_plan_from_manifest(Path(sys.argv[2]).read_bytes(), limits=limits())
def seam(point):
    """Coordinate a real operation boundary over pipes; abrupt exit retains all reservations."""
    if point == sys.argv[6]:
        print(point, flush=True)
        if sys.argv[7] == "die":
            os._exit(73)
        assert sys.stdin.readline().strip() == "continue"
refresh._fault = seam
vault._fault = seam
with RecordStore.open(sys.argv[1]) as store:
    try:
        result = refresh.refresh_readable_view(store, sys.argv[3], sys.argv[4], expected_plan=plan,
            new_plan=plan, source_root=sys.argv[5], protected_roots=[], limits=refresh_limits())
    except Exception as error:
        print("ERROR " + str(error), flush=True)
    else:
        print("SUCCESS " + result.attempt_path, flush=True)
'''


class RefreshRecoveryTests(RefreshFixture):
    """Separate processes exercise actual visibility barriers without sleeps or automatic recovery."""

    def child(self, point, destination, action="wait"):
        """Spawn candidate-relative bytecode-disabled Python with an independently opened store."""
        manifest = self.parent / "pinned.json"
        if not manifest.exists():
            manifest.write_bytes(self.plan.manifest_bytes)
            manifest.chmod(0o600)
        child = subprocess.Popen([sys.executable, "-B", "-c", PUBLISHER, str(self.runtime), str(manifest),
            str(self.view), str(destination), str(SOURCE), point, action], cwd=self.parent, env=child_environment(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop, child)
        return child

    def stop(self, child):
        """Reap only this fixture's child even if an assertion interrupts pipe coordination."""
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)

    def reached(self, child, expected):
        """Require a flushed real boundary within a deadline, without race-by-sleep assumptions."""
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(30), "child did not reach boundary")
        self.assertEqual(child.stdout.readline().strip(), expected)

    def inspect_attempt(self, attempt, destination):
        """Inspect retained siblings without requiring access to the store or old tree."""
        return inspect_readable_refresh(attempt, destination, source_root=SOURCE,
            protected_roots=[self.runtime], limits=refresh_limits())

    def test_abrupt_termination_at_each_boundary(self):
        """Every retained stage has an honest offline status, including complete output before ready."""
        prior, canonical, attempts = tree_state(self.view), metadata(self.runtime), set()
        points = ("after_attempt_reservation", "after_package_reservation", "after_intent", "after_preservation_file",
                  "after_successor", "after_complete_package", "after_ready", "before_rename", "at_rename",
                  "after_rename", "after_publication_sync", "after_published")
        for point in points:
            with self.subTest(point=point):
                destination = self.parent / point
                child = self.child(point, destination, "die")
                output, error = child.communicate(timeout=40)
                self.assertEqual(child.returncode, 73, output + error)
                fresh = set(self.parent.glob(".readable-refresh-attempt-*")) - attempts
                self.assertEqual(len(fresh), 1)
                attempt = fresh.pop()
                attempts.add(attempt)
                result = self.inspect_attempt(attempt, destination)
                expected = ("published" if point in ("after_rename", "after_publication_sync", "after_published") else
                    "complete_unpublished" if point in ("after_complete_package", "after_ready", "before_rename", "at_rename")
                    else "incomplete_preparation")
                self.assertEqual(result.status, expected, result.differences)
                self.assertEqual(result.historical_acknowledgment, "not_established")
                self.assertEqual(result.publication_observation, "present" if point == "after_published" else "absent")
                self.assertEqual(tree_state(self.view), prior)
                self.assertEqual(metadata(self.runtime), canonical)

    def test_two_refreshers_have_exactly_one_winner(self):
        """Kernel no-replace selects one complete package and leaves the losing package inspectable."""
        destination = self.parent / "competition"
        children = [self.child("at_rename", destination) for _ in range(2)]
        for child in children:
            self.reached(child, "at_rename")
        for child in children:
            child.stdin.write("continue\n")
            child.stdin.flush()
        outputs = []
        for child in children:
            output, error = child.communicate(timeout=40)
            self.assertEqual(child.returncode, 0, error)
            outputs.append(output)
        self.assertEqual(sum("SUCCESS " in value for value in outputs), 1, outputs)
        states = [self.inspect_attempt(a, destination) for a in self.parent.glob(".readable-refresh-attempt-*")]
        self.assertEqual(sorted(r.status for r in states), ["competing_destination", "published"])
        self.assertTrue(all(r.successor_path for r in states))

    def test_unrelated_competitors_are_not_traversed(self):
        """File/directory/symlink competitors remain untouched and never become this attempt's successor."""
        for kind in ("file", "directory", "symlink"):
            destination = self.parent / kind
            child = self.child("at_rename", destination)
            self.reached(child, "at_rename")
            if kind == "directory":
                destination.mkdir(mode=0o700)
            elif kind == "symlink":
                destination.symlink_to("absent")
            else:
                destination.write_bytes(b"competitor")
                destination.chmod(0o600)
            before = destination.lstat()
            output, error = child.communicate("continue\n", timeout=40)
            self.assertEqual(child.returncode, 0, error)
            self.assertIn("ERROR ", output)
            self.assertEqual(destination.lstat(), before)
            attempt = next(a for a in self.parent.glob(".readable-refresh-attempt-*")
                if json.loads((a / "intent.json").read_bytes())["destination"] == kind)
            result = self.inspect_attempt(attempt, destination)
            self.assertEqual(result.status, "competing_destination")
            self.assertNotEqual(result.verified_package_path, str(destination))

    def test_fresh_reader_across_rename_and_unavailable_originals(self):
        """Offline inspection works on both visibility sides and after moving away prior/store paths."""
        for point in ("at_rename", "after_rename"):
            destination = self.parent / point
            child = self.child(point, destination)
            self.reached(child, point)
            attempt = next(a for a in self.parent.glob(".readable-refresh-attempt-*")
                if json.loads((a / "intent.json").read_bytes())["destination"] == point)
            result = self.inspect_attempt(attempt, destination)
            self.assertEqual(result.status, "complete_unpublished" if point == "at_rename" else "published")
            output, error = child.communicate("continue\n", timeout=40)
            self.assertIn("SUCCESS ", output, error)
        self.store.close()
        self.runtime.rename(self.parent / "unavailable-runtime")
        self.view.rename(self.parent / "unavailable-prior")
        self.assertEqual(self.inspect_attempt(attempt, destination).status, "published")

    def test_corrupt_controls_payload_and_independent_identity(self):
        """Current malformed/contradictory controls and edited bytes cannot establish completion."""
        result = self.refresh()
        with self.assertRaises(ViewIntegrityError):
            self.inspect(result, expected_refresh_id="0" * 64)
        destination = Path(result.destination)
        for relative in ("refresh.json", "capture.json", "preservation-plan.json", "README.md", "generation/README.md"):
            path = destination / relative
            original = path.read_bytes()
            path.chmod(0o600)
            path.write_bytes(original + b" ")
            path.chmod(0o400)
            inspected = self.inspect(result)
            self.assertEqual(inspected.status, "inconsistent", relative)
            self.assertIsNone(inspected.successor_path)
            path.chmod(0o600)
            path.write_bytes(original)
            path.chmod(0o400)
        published = Path(result.attempt_path) / "published.json"
        original = published.read_bytes()
        published.chmod(0o600)
        published.write_bytes(original.replace(b'"version":1', b'"version":true'))
        published.chmod(0o400)
        self.assertEqual(self.inspect(result).status, "inconsistent")

    def test_inspection_rejects_unsafe_entries_and_caller_boundaries(self):
        """No-follow inspection refuses symlinks and traversal without writing or repairing anything."""
        result = self.refresh()
        with self.assertRaises(ViewLayoutError):
            inspect_readable_refresh(result.attempt_path, Path(result.destination) / "../successor", source_root=SOURCE,
                                     protected_roots=[], limits=refresh_limits())
        root = Path(result.destination)
        root.chmod(0o700)
        (root / "extra").symlink_to(self.runtime)
        before = tree_state(root)
        with self.assertRaises(ViewLayoutError):
            self.inspect(result)
        self.assertEqual(tree_state(root), before)

    def test_coherently_rehashed_preservation_omission_is_rejected(self):
        """An omitted proposed edit cannot be hidden by rehashing the supplied plan/package/evidence."""
        import hashlib
        self.write("human.md", b"preserve this exact proposed edit\n")
        result = self.refresh()
        root, attempt = Path(result.destination), Path(result.attempt_path)
        def encoded(value):
            """Reproduce canonical JSON only to simulate a coherent untrusted metadata rewrite."""
            return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        def digest(data):
            """Hash attacker-selected bytes without implying historical authenticity."""
            return hashlib.sha256(data).hexdigest()
        def rewrite(path, data):
            """Replace mutable test-owned control bytes and restore their expected safe mode."""
            path.chmod(0o600)
            path.write_bytes(data)
            path.chmod(0o400)
        preservation = json.loads((root / "preservation-plan.json").read_bytes())
        removed = next(r for r in preservation["files"] if r["source_path"] == "human.md")
        preservation["files"].remove(removed)
        preservation["preservation_plan_id"] = digest(encoded({k: v for k, v in preservation.items() if k != "preservation_plan_id"}))
        plan_data = encoded(preservation)
        rewrite(root / "preservation-plan.json", plan_data)
        (root / "preservation" / removed["preservation_path"]).unlink()
        manifest = json.loads((root / "refresh.json").read_bytes())
        manifest["preservation"].update(preservation_plan_id=preservation["preservation_plan_id"],
                                        sha256=digest(plan_data), size=len(plan_data))
        manifest["files"] = [r for r in manifest["files"] if r["path"] != "preservation/" + removed["preservation_path"]]
        for row in manifest["files"]:
            if row["path"] == "preservation-plan.json":
                row.update(sha256=digest(plan_data), size=len(plan_data))
        manifest["refresh_id"] = digest(encoded({k: v for k, v in manifest.items() if k != "refresh_id"}))
        manifest_data = encoded(manifest)
        rewrite(root / "refresh.json", manifest_data)
        for name in ("intent.json", "ready.json", "published.json"):
            value = json.loads((attempt / name).read_bytes())
            value.update(refresh_id=manifest["refresh_id"], manifest_sha256=digest(manifest_data))
            if name == "intent.json":
                value["preservation_plan_id"] = preservation["preservation_plan_id"]
            rewrite(attempt / name, encoded(value))
        inspected = self.inspect(result)
        self.assertEqual(inspected.status, "inconsistent")
        self.assertIsNone(inspected.successor_path)

    def test_private_recovery_metadata_retains_only_established_identities(self):
        """Interrupts before and after rename retain exact independent plan and capture associations."""
        for index, boundary in enumerate(("after_attempt_reservation", "after_ready", "after_rename")):
            destination = self.parent / ("structured-" + str(index))
            def interrupt(point):
                """Raise KeyboardInterrupt only at the selected actual publication seam."""
                if point == boundary:
                    raise KeyboardInterrupt()
            with patch("research_pipeline.view_refresh._fault", interrupt), self.assertRaises(KeyboardInterrupt) as caught:
                self.refresh(destination)
            facts = caught.exception._readable_recovery
            self.assertEqual(facts["destination"], str(destination))
            self.assertEqual(facts["prior_plan_id"], self.plan.plan_id)
            self.assertEqual(facts["successor_plan_id"], self.plan.plan_id)
            self.assertEqual(facts["rename_entered"], boundary == "after_rename")
            self.assertFalse(facts["collision"])
            for name in ("capture_id", "preservation_plan_id", "refresh_id", "manifest_sha256"):
                self.assertRegex(facts[name], r"^[0-9a-f]{64}$")
                self.assertNotEqual(facts[name], "0" * 64)
            attempt = Path(facts["attempt_path"])
            expected = attempt.with_name(attempt.name.replace(".readable-refresh-attempt-", ".readable-refresh-package-"))
            self.assertEqual(facts["preparation_path"], str(expected))
