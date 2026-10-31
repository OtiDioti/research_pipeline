"""Saved-package codecs, binding gates and retained publication evidence using real private files."""

from copy import deepcopy
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from research_pipeline import checkout, cli_controls, cli_proposals as packages
from research_pipeline.cli import _LIMITS, _classify
from research_pipeline.cli_controls import CliError, read_request
from research_pipeline.domain import DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError
from research_pipeline.store import RevisionConflictError, SubmissionConflictError, ReferenceResolutionError
from research_pipeline.work_product_import import _METADATA, prepare_work_product_import
from tests import test_checkout as checkout_tests
from tests.test_store import CREATOR, CONTROLLER


class PackageTests(unittest.TestCase):
    """Exercise actual saved bytes without relying on a live store for package inspection."""

    def setUp(self):
        """Seed the accepted library fixture and generate one detached preview for package-only tests."""
        checkout_tests.CheckoutTests.setUp(self)
        self.info = checkout_tests.CheckoutTests.run_checkout(self)
        self.metadata = {key: self.value.to_dict()[key] for key in _METADATA}
        self.selected = [entry.path for entry in self.value.files]
        self.arguments = SimpleNamespace(**{name: default for name, (default, _, _, _) in _LIMITS.items()})
        self.prepared = prepare_work_product_import(
            self.store, self.base, self.destination, expected_head=1, metadata=self.metadata,
            selected_paths=self.selected, submission_id="edited", record_provenance=CREATOR,
            submission_provenance=CREATOR, max_inventory_entries=100, **self.options)
        self.documents = packages.documents(self.prepared, self.info, CONTROLLER, self.arguments)
        self.package = self.parent / "saved"
        self.effects = {"begun": True, "operation": "prepare-work-product"}

    def publish(self):
        """Publish this fixture through real exclusive writes and full content/durability gates."""
        return packages.publish(self.package, self.documents, self.arguments, self.effects)

    def observe(self, durable=False):
        """Inspect the selected package or establish current input durability without submitting."""
        return packages.observe(self.package, self.arguments, durable=durable)

    def rewrite(self, name, data):
        """Simulate owner mutation of a disposable leaf, preserving the required final private mode."""
        path = self.package / name
        path.chmod(0o600)
        path.write_bytes(data)
        path.chmod(0o400)

    def rebind_summary(self, value):
        """Update both summary bytes and their manifest digest to test semantic comparisons beyond hashing."""
        data = packages._json(value, self.arguments.max_summary_bytes)
        self.rewrite("summary.json", data)
        manifest = json.loads((self.package / packages._CONTROL / "manifest.json").read_bytes())
        manifest["summary"] = packages._digest(data)
        self.rewrite(packages._CONTROL + "/manifest.json", packages._json(manifest, 16384))

    def test_exact_documents_and_detached_durable_observation(self):
        """Saved ASCII bytes/hash/identities and complete proposals survive store close without artifact reads."""
        expected = self.publish()
        self.store.close()
        with patch.object(checkout, "_sync", side_effect=AssertionError("inspection synchronized")):
            actual, submission = self.observe()
        self.assertEqual(expected, actual)
        self.assertEqual(actual["state"], "published")
        self.assertEqual(actual["historical_durability"], "unknown")
        self.assertEqual(submission.to_dict(), self.prepared.submission.to_dict())
        for name, data in self.documents.items():
            path = self.package / (packages._CONTROL if name == "manifest.json" else "") / name
            self.assertEqual(path.read_bytes(), data)
            self.assertTrue(data.isascii())
            self.assertFalse(data.endswith(b"\n"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o400)
        self.assertEqual(actual["proposal_sha256"], hashlib.sha256(self.documents["proposal.json"]).hexdigest())
        self.assertEqual(self.observe(durable=True)[0], actual)

    def test_exact_byte_boundaries(self):
        """Proposal, summary, manifest and actual read bounds accept equality and reject one byte less."""
        self.publish()
        for option, name in (("max_proposal_bytes", "proposal.json"), ("max_summary_bytes", "summary.json"),
                             ("max_control_bytes", "manifest.json")):
            old = getattr(self.arguments, option)
            setattr(self.arguments, option, len(self.documents[name]))
            self.observe()
            packages.documents(self.prepared, self.info, CONTROLLER, self.arguments)
            setattr(self.arguments, option, len(self.documents[name]) - 1)
            with self.assertRaises(SnapshotLimitError):
                self.observe()
            with self.assertRaises(SnapshotLimitError):
                packages.documents(self.prepared, self.info, CONTROLLER, self.arguments)
            setattr(self.arguments, option, old)

    def assert_saved_bytes(self, path):
        """Check all three retained package documents against the exact originally prepared bytes."""
        for name, data in self.documents.items():
            location = path / (packages._CONTROL if name == "manifest.json" else "") / name
            self.assertEqual(location.read_bytes(), data)

    def test_initial_absence_with_stable_ancestors(self):
        """Only never-observed missing package/path components yield offline absence or durable status 3."""
        for path in (self.package, self.parent / "missing-parent" / "saved"):
            with self.subTest(path=path):
                result, submission = packages.observe(path, self.arguments)
                self.assertEqual(result["state"], "absent")
                self.assertEqual(result["historical_durability"], "unknown")
                self.assertIsNone(submission)
                with self.assertRaises(CliError) as caught:
                    packages.observe(path, self.arguments, durable=True)
                self.assertEqual((caught.exception.status, caught.exception.code), (3, "missing"))

    def test_directory_disappears_or_is_replaced_after_initial_stat(self):
        """Real renames across both observation/open boundaries conflict and retain the original bytes."""
        for durable in (False, True):
            for boundary in ("initial_stat", "open"):
                for replacement in ("absent", "directory", "symlink", "file"):
                    with self.subTest(durable=durable, boundary=boundary, replacement=replacement):
                        self.package = self.parent / f"saved-{durable}-{boundary}-{replacement}"
                        retained = self.package.with_name(self.package.name + "-retained")
                        self.publish()
                        original_stat, original_open = checkout._stat, os.open
                        observed, fired = False, False

                        def mutate():
                            """Retain the real observed directory and install the selected competing binding."""
                            nonlocal fired
                            self.assertTrue(observed)
                            fired = True
                            self.package.rename(retained)
                            if replacement == "directory":
                                self.package.mkdir(mode=0o700)
                            elif replacement == "symlink":
                                self.package.symlink_to(retained, target_is_directory=True)
                            elif replacement == "file":
                                self.package.write_bytes(b"competitor")
                                self.package.chmod(0o600)

                        def observe_stat(parent, name):
                            """Return a real initial stat, mutating only after its successful observation."""
                            nonlocal observed
                            result = original_stat(parent, name)
                            if name == self.package.name and not fired:
                                observed = True
                                if boundary == "initial_stat":
                                    mutate()
                            return result

                        def open_directory(name, flags, *args, **kwargs):
                            """Rename after the real stats but before delegating the actual no-follow open."""
                            if name == self.package.name and not fired and boundary == "open":
                                mutate()
                            return original_open(name, flags, *args, **kwargs)

                        with patch.object(checkout, "_stat", observe_stat), patch.object(os, "open", open_directory):
                            with self.assertRaises(CliError) as caught:
                                self.observe(durable=durable)
                        self.assertTrue(fired)
                        self.assertEqual((caught.exception.status, caught.exception.code), (4, "conflict"))
                        self.assert_saved_bytes(retained)
                        if replacement == "directory":
                            self.assertEqual(list(self.package.iterdir()), [])
                        elif replacement == "file":
                            self.assertEqual(self.package.read_bytes(), b"competitor")

    def test_held_bindings_disappear_during_recheck(self):
        """Later leaf reads cannot hide loss of a held package or ancestor directory binding."""
        for durable in (False, True):
            for ancestor in (False, True):
                container = self.parent / f"container-{durable}-{ancestor}"
                container.mkdir(mode=0o700)
                self.package = container / "saved"
                self.publish()
                target = container if ancestor else self.package
                retained = target.with_name(target.name + "-retained")
                fired = False

                def fault(boundary):
                    """Detach an already-held directory just before the real final binding checks."""
                    nonlocal fired
                    if boundary == "after_summary.json" and not fired:
                        fired = True
                        target.rename(retained)

                with patch.object(packages, "_fault", fault), self.assertRaises(CliError) as caught:
                    self.observe(durable=durable)
                self.assertTrue(fired)
                self.assertEqual((caught.exception.status, caught.exception.code), (4, "conflict"))
                self.assert_saved_bytes(retained / "saved" if ancestor else retained)

    def test_missing_child_does_not_hide_lost_ancestor(self):
        """Before reporting initial child absence, recheck held ancestors for disappearance/substitution."""
        for durable in (False, True):
            for replacement in (False, True):
                container = self.parent / f"ancestor-{durable}-{replacement}"
                container.mkdir(mode=0o700)
                self.package = container / "missing"
                retained = container.with_name(container.name + "-retained")
                original_stat, fired = checkout._stat, False

                def missing(parent, name):
                    """Detach the held ancestor before the real stat of its never-observed missing child."""
                    nonlocal fired
                    if name == "missing" and not fired:
                        fired = True
                        container.rename(retained)
                        if replacement:
                            container.mkdir(mode=0o700)
                    return original_stat(parent, name)

                with patch.object(checkout, "_stat", missing), self.assertRaises(CliError) as caught:
                    self.observe(durable=durable)
                self.assertTrue(fired)
                self.assertEqual((caught.exception.status, caught.exception.code), (4, "conflict"))
                self.assertEqual(list(retained.iterdir()), [])

    def test_missing_internal_control_after_inventory_is_conflict(self):
        """A control seen by inventory cannot become selected-package absence before directory opening."""
        self.publish()
        control = self.package / packages._CONTROL
        retained = self.parent / "retained-control"
        original_stat = checkout._stat
        for durable in (False, True):
            fired = False

            def missing(parent, name):
                """Move control evidence after root enumeration and before its initial no-follow stat."""
                nonlocal fired
                if name == packages._CONTROL and not fired:
                    fired = True
                    control.rename(retained)
                return original_stat(parent, name)

            with patch.object(checkout, "_stat", missing), self.assertRaises(CliError) as caught:
                self.observe(durable=durable)
            self.assertTrue(fired)
            self.assertEqual((caught.exception.status, caught.exception.code), (4, "conflict"))
            retained.rename(control)
            self.assert_saved_bytes(self.package)

    def test_directory_permission_failure_is_not_absence(self):
        """Permission denial at initial stat or actual opening stays an operational error with retained bytes."""
        self.publish()
        for durable in (False, True):
            for initial in (False, True):
                original_stat, original_open = checkout._stat, os.open
                fired = False

                def denied_stat(parent, name):
                    """Deny only the selected directory's initial stat; ancestors remain accessible."""
                    nonlocal fired
                    if initial and name == self.package.name:
                        fired = True
                        raise PermissionError(errno.EACCES, "fixture denied")
                    return original_stat(parent, name)

                def denied_open(name, flags, *args, **kwargs):
                    """Deny only the selected directory's delegated open after successful real stats."""
                    nonlocal fired
                    if not initial and name == self.package.name:
                        fired = True
                        raise PermissionError(errno.EACCES, "fixture denied")
                    return original_open(name, flags, *args, **kwargs)

                with patch.object(checkout, "_stat", denied_stat), patch.object(os, "open", denied_open):
                    with self.assertRaises((PermissionError, checkout.CheckoutOperationalError)) as caught:
                        self.observe(durable=durable)
                self.assertTrue(fired)
                classified = _classify(caught.exception, dict(begun=False, operation="inspect-proposal"))
                self.assertEqual((classified.status, classified.code), (6, "operational_error"))
                self.assert_saved_bytes(self.package)

    def test_publication_verification_absence_is_conflict_or_uncertainty(self):
        """Losing a reserved package before verification conflicts; publication retains uncertainty precedence."""
        for boundary in ("wrote_manifest.json", "published"):
            self.package = self.parent / boundary
            retained = self.parent / (boundary + "-retained")
            self.effects = dict(begun=True, operation="prepare-work-product")
            fired = False

            def fault(current):
                """Retain the reserved package at a real boundary before fresh verification opens it."""
                nonlocal fired
                if current == boundary:
                    fired = True
                    self.package.rename(retained)

            with patch.object(packages, "_fault", fault), self.assertRaises(CliError) as caught:
                self.publish()
            self.assertTrue(fired)
            self.assertEqual(caught.exception.status, 4)
            self.assertEqual(_classify(caught.exception, self.effects).status, 7 if boundary == "published" else 4)
            self.assert_saved_bytes(retained)

    def test_saved_leaves_disappear_before_open_or_during_read(self):
        """Observed leaf renames conflict in offline/durable reads while preserving every document's bytes."""
        self.publish()
        original_read = packages.read_control
        for durable in (False, True):
            for name in self.documents:
                for boundary in ("before_control_open", "after_control_read"):
                    with self.subTest(durable=durable, name=name, boundary=boundary):
                        path = self.package / (packages._CONTROL if name == "manifest.json" else "") / name
                        retained = self.parent / (name + "-retained")
                        fired = False

                        def rename(current):
                            """Remove only the selected observed leaf's binding, retaining its real inode outside."""
                            nonlocal fired
                            if current == boundary and not fired:
                                fired = True
                                path.rename(retained)

                        def read_selected(parent, leaf, location, maximum, *, modes):
                            """Arm the real reader's seam only for the intended saved document."""
                            if location == path:
                                with patch.object(cli_controls, "_fault", rename):
                                    return original_read(parent, leaf, location, maximum, modes=modes)
                            return original_read(parent, leaf, location, maximum, modes=modes)

                        with patch.object(packages, "read_control", read_selected):
                            with self.assertRaises(CliError) as caught:
                                self.observe(durable=durable)
                        self.assertTrue(fired)
                        self.assertEqual((caught.exception.status, caught.exception.code), (4, "conflict"))
                        self.assertEqual(str(caught.exception),
                                         "Saved package bindings or contents changed during observation.")
                        self.assertFalse(path.exists())
                        self.assertEqual(retained.read_bytes(), self.documents[name])
                        for other, data in self.documents.items():
                            if other != name:
                                location = self.package / (packages._CONTROL if other == "manifest.json" else "") / other
                                self.assertEqual(location.read_bytes(), data)
                        # Restore only as fixture reset; observation must never recreate the leaf.
                        retained.rename(path)

    def test_saved_leaf_open_permission_and_io_failures_remain_operational(self):
        """Real successful stats followed by EACCES/EIO at open stay operational for inspect and submit."""
        self.publish()
        original_read, original_open = packages.read_control, os.open
        for durable in (False, True):
            for name in self.documents:
                for number in (errno.EACCES, errno.EIO):
                    with self.subTest(durable=durable, name=name, errno=number):
                        path = self.package / (packages._CONTROL if name == "manifest.json" else "") / name
                        fired = False
                        failure = OSError(number, "fixture open failure")

                        def fail_open(leaf, flags, *args, **kwargs):
                            """Inject I/O failure only at the selected reader's real open after its stat gates."""
                            nonlocal fired
                            if leaf == name:
                                fired = True
                                raise failure
                            return original_open(leaf, flags, *args, **kwargs)

                        def read_selected(parent, leaf, location, maximum, *, modes):
                            """Restrict the failing open to the selected saved document's production reader."""
                            if location == path:
                                with patch.object(os, "open", fail_open):
                                    return original_read(parent, leaf, location, maximum, modes=modes)
                            return original_read(parent, leaf, location, maximum, modes=modes)

                        with patch.object(packages, "read_control", read_selected):
                            with self.assertRaises(checkout.CheckoutOperationalError) as caught:
                                self.observe(durable=durable)
                        self.assertTrue(fired)
                        self.assertIs(caught.exception.__cause__, failure)
                        operation = "submit-work-product" if durable else "inspect-proposal"
                        classified = _classify(caught.exception, dict(begun=False, operation=operation))
                        self.assertEqual((classified.status, classified.code), (6, "operational_error"))
                        self.assert_saved_bytes(self.package)

    def test_retained_states_and_no_automatic_finishing(self):
        """Early reservations and complete unpublished packages are inspectable but never submittable."""
        self.assertEqual(self.observe()[0]["state"], "absent")
        for boundary, state in (("reserved", "incomplete"), ("marked", "incomplete"),
                                ("wrote_proposal.json", "incomplete"),
                                ("before_publish", "complete_unpublished"), ("published", "published")):
            self.package = self.parent / boundary
            def fault(current):
                """Stop at a deterministic real lifecycle boundary, retaining all created evidence."""
                if current == boundary:
                    raise OSError("fixture interruption")
            with patch.object(packages, "_fault", fault), self.assertRaises(OSError):
                self.publish()
            result, _ = self.observe()
            self.assertEqual(result["state"], state)
            before = sorted(str(path.relative_to(self.package)) for path in self.package.rglob("*"))
            if state != "published":
                with self.assertRaises(CliError) as caught:
                    self.observe(durable=True)
                self.assertEqual(caught.exception.status, 5)
            self.assertEqual(sorted(str(path.relative_to(self.package)) for path in self.package.rglob("*")), before)
            if state == "incomplete":
                self.assertIsNone(result["proposal"])
                self.assertIsNone(result["submission_id"])

    def test_conflicting_hash_identity_summary_and_inventory(self):
        """Coherent JSON with mismatched hashes, recomputed changes or manifest identities is conflict."""
        self.publish()
        original = json.loads(self.documents["summary.json"])
        for field, value in (("proposed_revision", 3), ("old_files", []), ("metadata_changes", {"title": {"before": "wrong", "after": "different"}}),
                             ("provenance_changes", {"record": {"before": CREATOR.to_dict(),
                                                                "after": CONTROLLER.to_dict()}}), ("paths", []),
                             ("structural_changes", {**original["changes"]["structural_changes"],
                                                     "revision": {"before": 1, "after": 3}})):
            mutated = deepcopy(original)
            mutated["changes"][field] = value
            self.rebind_summary(mutated)
            with self.assertRaises(CliError) as caught:
                self.observe()
            self.assertEqual(caught.exception.status, 4)
        self.rebind_summary(original)
        manifest_path = packages._CONTROL + "/manifest.json"
        manifest = json.loads(self.documents["manifest.json"])
        for field, value in (("submission_id", "other"), ("record_id", "other"), ("base_revision", 2),
                             ("proposed_revision", 3), ("proposal", {"sha256": "0" * 64, "bytes": 1})):
            mutated = {**manifest, field: value}
            self.rewrite(manifest_path, packages._json(mutated, 16384))
            with self.assertRaises(CliError):
                self.observe()
        self.rewrite(manifest_path, self.documents["manifest.json"])
        (self.package / "unexpected").mkdir(mode=0o700)
        with self.assertRaises(CliError):
            self.observe()

    def test_strict_summary_report(self):
        """Unselected entries require exact fields, types, ordering and opaque/escaped relationships."""
        self.publish()
        baseline = json.loads(self.documents["summary.json"])
        entry = dict(path="unused", path_escaped=False, kind="file", opaque=False)
        invalid = [None, [{**entry, "opaque": True}], [{**entry, "path_escaped": 0}],
                   [{**entry, "extra": 1}], [{**entry, "kind": "unknown"}],
                   [{**entry, "path": "../escape"}], [{**entry, "path_escaped": True}],
                   [entry, entry], [{**entry, "path": "z"}, entry]]
        for report in invalid:
            value = deepcopy(baseline)
            value["changes"]["unselected_material"] = report
            self.rebind_summary(value)
            with self.assertRaises(DomainValidationError):
                self.observe()

    def test_malformed_available_evidence_is_not_incomplete(self):
        """Partial documents, duplicate fields, coercive tokens and noncanonical proposal bytes fail closed."""
        self.publish()
        path = self.package / packages._CONTROL / "incomplete"
        path.touch(mode=0o400)
        for data in (b'{', b'{"version":1,"version":1}', b'[' * 65 + b']' * 65,
                     self.documents["proposal.json"] + b'\n', b'{"x":' + b'1' * 129 + b'}',
                     b'{"x":"\\ud800"}'):
            self.rewrite("proposal.json", data)
            with self.assertRaises((CliError, DomainValidationError)):
                self.observe()
        self.rewrite("proposal.json", self.documents["proposal.json"])
        path.chmod(0o600)
        path.write_bytes(b"not empty")
        path.chmod(0o400)
        with self.assertRaises(SnapshotLimitError):
            self.observe()

    def test_unsafe_leaves_and_ancestors(self):
        """Links, FIFOs, sockets and wrong modes fail before any unsafe content can be consumed."""
        self.publish()
        path = self.package / "proposal.json"
        for kind in ("symlink", "hardlink", "fifo", "socket", "mode"):
            path.unlink()
            sock = None
            if kind == "symlink":
                path.symlink_to(self.package / "summary.json")
            elif kind == "hardlink":
                os.link(self.package / "summary.json", path)
            elif kind == "fifo":
                os.mkfifo(path, 0o400)
            elif kind == "socket":
                sock = socket.socket(socket.AF_UNIX)
                previous = Path.cwd()
                try:
                    os.chdir(self.package)
                    sock.bind(path.name)
                finally:
                    os.chdir(previous)
                    sock.close()
                path.chmod(0o400)
            else:
                path.write_bytes(self.documents["proposal.json"])
                path.chmod(0o600)
            try:
                with self.assertRaises(checkout.CheckoutLayoutError):
                    self.observe()
            finally:
                if sock:
                    sock.close()
        path.chmod(0o400)
        self.package.chmod(0o755)
        with self.assertRaises(checkout.CheckoutLayoutError):
            self.observe()
        self.package.chmod(0o700)
        alias = self.parent / "alias"
        alias.symlink_to(self.package, target_is_directory=True)
        with self.assertRaises(checkout.CheckoutLayoutError):
            packages.observe(alias, self.arguments)

    def test_cross_file_replacement_and_postsync_mutation(self):
        """Equal-byte replacement of an earlier leaf and postbarrier mutation cannot pass final gates."""
        self.publish()
        for boundary in ("after_summary.json", "after_input_sync"):
            def fault(current):
                """Replace the already observed proposal with equal bytes before the real binding gate."""
                if current == boundary:
                    path = self.package / "proposal.json"
                    data = path.read_bytes()
                    path.unlink()
                    path.write_bytes(data)
                    path.chmod(0o400)
            with patch.object(packages, "_fault", fault), self.assertRaises(CliError):
                self.observe(durable=boundary == "after_input_sync")

    def test_read_growth_truncation_and_equal_replacement(self):
        """Actual read/EOF and preopen signatures detect mutation without relying only on stat lengths."""
        self.publish()
        path = self.package / "proposal.json"
        for action in ("grow", "truncate", "replace"):
            self.rewrite("proposal.json", self.documents["proposal.json"])
            fired = False
            def fault(boundary):
                """Change the selected regular leaf after lstat or after its first bounded read."""
                nonlocal fired
                if not fired and boundary == ("before_control_open" if action == "replace" else "chunk_read"):
                    fired = True
                    data = path.read_bytes()
                    if action == "replace":
                        path.unlink()
                        path.write_bytes(data)
                        path.chmod(0o400)
                    else:
                        self.rewrite("proposal.json", data + b"x" if action == "grow" else b"")
            with patch("research_pipeline.cli_controls._fault", fault), self.assertRaises(CliError):
                self.observe()

    def test_exclusive_collisions_preserve_competitors(self):
        """Existing destinations and leaf-creation races retain competitor bytes instead of adopting them."""
        self.package.mkdir(mode=0o700)
        with self.assertRaises(checkout.CheckoutLayoutError):
            self.publish()
        self.assertEqual(list(self.package.iterdir()), [])
        self.package = self.parent / "race"
        def fault(boundary):
            """Install a competing leaf after reservation and before exclusive payload creation."""
            if boundary == "marked":
                (self.package / "proposal.json").write_bytes(b"competitor")
        with patch.object(packages, "_fault", fault), self.assertRaises(checkout.CheckoutOperationalError):
            self.publish()
        self.assertEqual((self.package / "proposal.json").read_bytes(), b"competitor")
        self.assertTrue((self.package / packages._CONTROL / "incomplete").exists())

    def test_short_zero_writes_sync_unlink_and_close(self):
        """Complete writes drain short progress; failures retain evidence and never silently publish."""
        original_write = os.write
        def short(fd, data):
            """Write at most seven bytes to exercise the actual complete-write loop."""
            return original_write(fd, data[:7])
        with patch.object(os, "write", short):
            self.publish()
        self.observe()
        for failure in ("write", "sync", "unlink", "close"):
            self.package = self.parent / failure
            if failure == "write":
                target = "os.write"
                def replacement(fd, data):
                    """Report zero write progress without consuming the proposed bytes."""
                    return 0
            elif failure == "sync":
                target, replacement = "os.fsync", OSError("sync failure")
            elif failure == "unlink":
                target, replacement = "os.unlink", OSError("unlink failure")
            else:
                target, replacement = "research_pipeline.cli_proposals._fault", None
                def replacement(boundary):
                    """Inject a reported resource-close failure only after actual publication gates."""
                    if boundary == "before_close":
                        raise OSError("close failure")
            with patch(target, side_effect=replacement), self.assertRaises((OSError, checkout.CheckoutOperationalError)):
                self.publish()
            if failure == "unlink":
                self.assertEqual(self.observe()[0]["state"], "complete_unpublished")
            if failure == "close":
                self.assertEqual(self.observe()[0]["state"], "published")

    def test_no_publish_after_final_gate_mutation(self):
        """Mutation after synchronization is detected by the full gate immediately before marker removal."""
        def fault(boundary):
            """Replace the summary after barriers while preserving equal bytes to challenge signatures."""
            if boundary == "before_publish":
                path = self.package / "summary.json"
                data = path.read_bytes()
                path.unlink()
                path.write_bytes(data)
                path.chmod(0o400)
        with patch.object(packages, "_fault", fault), self.assertRaises(CliError):
            self.publish()
        self.assertTrue((self.package / packages._CONTROL / "incomplete").exists())

    def test_complete_request_preflight(self):
        """All authored fields and nested defaults are checked without needing draft contents or a store."""
        path = self.parent / "request.json"
        value = dict(format="research_pipeline.cli_work_product_preparation", version=1,
                     base=self.base.to_dict(), expected_head=1, metadata=self.metadata,
                     selected_paths=self.selected, submission_id="edit", record_provenance=CREATOR.to_dict(),
                     submission_provenance=CREATOR.to_dict())
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        self.assertEqual(read_request(path, path.stat().st_size, 4)["base"], self.base)
        with self.assertRaises(SnapshotLimitError):
            read_request(path, path.stat().st_size - 1, 4)
        variants = [{**value, "version": True}, {**value, "expected_head": 1.0},
                    {**value, "runtime": "/unused"}, {**value, "selected_paths": []},
                    {**value, "selected_paths": [".WORK-PRODUCT/control"]},
                    {**value, "record_provenance": {"actor": CREATOR.actor, "created_at": CREATOR.created_at}},
                    {**value, "metadata": {**self.metadata, "generated_status": "accepted"}}]
        for field in value:
            variants.append({key: item for key, item in value.items() if key != field})
        for altered in variants:
            path.write_text(json.dumps(altered))
            with self.assertRaises((DomainValidationError, CliError)):
                read_request(path, 100000, 4)

    def test_operation_specific_classification(self):
        """Known typed conflicts and integrity refusals remain definite; entered unknown failures are uncertain."""
        effects = dict(begun=True, submit_entered=True, operation="submit-work-product")
        for error, status in ((RevisionConflictError(), 4), (SubmissionConflictError(), 4),
                              (ReferenceResolutionError(), 6), (RuntimeError(), 7),
                              (KeyboardInterrupt(), 7)):
            self.assertEqual(_classify(error, effects).status, status)
        self.assertEqual(_classify(DomainValidationError(), {**effects, "returned": True}).status, 7)

    def test_dispatch_preparation_and_exact_submission(self):
        """Exercise command orchestration with explicit fixture source exclusion; subprocess tests verify derivation."""
        from research_pipeline import cli
        config = self.parent / "config.json"
        config.write_text(json.dumps(dict(format="research_pipeline.cli_config", version=1,
                                         store=str(self.root), protected_roots=[])))
        config.chmod(0o600)
        request = self.parent / "request.json"
        request.write_text(json.dumps(dict(format="research_pipeline.cli_work_product_preparation", version=1,
                          base=self.base.to_dict(), expected_head=1, metadata=self.metadata,
                          selected_paths=self.selected, submission_id="dispatch", record_provenance=CREATOR.to_dict(),
                          submission_provenance=CONTROLLER.to_dict())))
        request.chmod(0o600)
        context = dict(store=None, destination=str(self.package), record_id=None, revision=None,
                       submission_id=None, next_action=None)
        arguments = cli._parser().parse_args(["prepare-work-product", "--config", str(config),
                    "--checkout", str(self.destination), "--request", str(request),
                    "--destination", str(self.package)])
        cli._validate(arguments)
        before = checkout_tests.CheckoutTests.snapshot(self)[0]
        with patch.object(cli, "source_root", return_value=self.source_tree):
            output, status = cli._execute(arguments, context, self.effects)
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output)["result"]["submission_id"], "dispatch")
        self.assertEqual(checkout_tests.CheckoutTests.snapshot(self)[0], before)
        arguments = cli._parser().parse_args(["submit-work-product", "--config", str(config),
                                              "--proposal", str(self.package)])
        cli._validate(arguments)
        effects = dict(begun=False, operation="submit-work-product")
        with patch.object(cli, "source_root", return_value=self.source_tree):
            output, status = cli._execute(arguments, context, effects)
        self.assertEqual(status, 0)
        receipt = json.loads(output)["result"]["receipt"]
        self.assertEqual(receipt, self.store.get_submission("dispatch").to_dict())
        with patch.object(cli, "source_root", return_value=self.source_tree):
            retry, status = cli._execute(arguments, context, effects)
        self.assertEqual(retry, output)
        self.assertEqual(self.store.get_revision("bundle", 1), self.envelope)

    def test_arbitrary_proposals_and_generated_status_are_refused(self):
        """The package route retains the accepted one-work-product immediate-predecessor CAS restriction."""
        self.publish()
        original = json.loads(self.documents["proposal.json"])
        variants = [original["submission"], {**original, "version": True}]
        for field, value in (("operational_status", "completed"), ("scientific_disposition", "accepted"),
                             ("kind", "claim"), ("revision", 3)):
            altered = deepcopy(original)
            altered["submission"]["records"][0][field] = value
            variants.append(altered)
        altered = deepcopy(original)
        altered["submission"]["expected_heads"] = {"bundle": 0}
        variants.append(altered)
        for altered in variants:
            self.rewrite("proposal.json", packages._json(altered, self.arguments.max_proposal_bytes))
            with self.assertRaises(DomainValidationError):
                self.observe()

    def test_request_hostile_json_and_unsafe_controls(self):
        """Authored controls use strict pre-codec depth/token/scalar gates and reject unsafe leaves before reads."""
        path = self.parent / "hostile.json"
        for data in (b'{"format":1,"format":2}', b'[' * 65 + b']' * 65,
                     b'{"x":' + b'9' * 129 + b'}', b'{"x":1e999}', b'{"x":NaN}',
                     b'{"x":"\\ud800"}', b'\xff'):
            path.write_bytes(data)
            path.chmod(0o600)
            with self.assertRaises((CliError, DomainValidationError, SnapshotLimitError)):
                read_request(path, 100000, 4)
        path.unlink()
        os.mkfifo(path, 0o600)
        with self.assertRaises(checkout.CheckoutLayoutError):
            read_request(path, 100000, 4)

    def test_input_close_and_synchronization_failures(self):
        """Durable observation fails before returning a detached request when synchronization or close fails."""
        self.publish()
        with patch.object(os, "fsync", side_effect=OSError("sync failed")):
            with self.assertRaises(checkout.CheckoutOperationalError):
                self.observe(durable=True)
        original_close = os.close
        armed = False
        def fault(boundary):
            """Arm a close failure only after actual saved-input durability barriers."""
            nonlocal armed
            if boundary == "after_input_sync":
                armed = True
        def close(fd):
            """Close actual descriptors and then report failure, preserving retained evidence."""
            original_close(fd)
            if armed:
                raise OSError("reported close failure")
        with patch.object(packages, "_fault", fault), patch.object(os, "close", close):
            with self.assertRaises((OSError, checkout.CheckoutOperationalError)):
                self.observe(durable=True)
        self.assertEqual(self.observe()[0]["state"], "published")
