"""Fresh-process CLI draft round trips, exact retries and real interrupted acknowledgment."""

import json
import os
from pathlib import Path
import shutil
import unittest

from research_pipeline.work_product_import import _METADATA
from tests import test_cli_operations as operations
from tests.test_store import CREATOR, CONTROLLER


class SavedCliTests(unittest.TestCase):
    """Reuse private store fixtures and execute only candidate-relative production CLI entry points."""

    invoke = operations.CliOperationTests.invoke
    diagnostic = operations.CliOperationTests.diagnostic
    snapshot = operations.CliOperationTests.snapshot
    write_config = operations.CliOperationTests.write_config

    def setUp(self):
        """Seed initial canonical data and explicit private controls; all subsequent changes use the CLI."""
        operations.CliOperationTests.setUp(self)
        self.package = self.parent / "saved"
        self.request_path = self.parent / "request.json"
        self.request_value = dict(format="research_pipeline.cli_work_product_preparation", version=1,
                                  base=self.base.to_dict(), expected_head=1,
                                  metadata={key: self.value.to_dict()[key] for key in _METADATA},
                                  selected_paths=[entry.path for entry in self.value.files], submission_id="edited",
                                  record_provenance=CREATOR.to_dict(), submission_provenance=CONTROLLER.to_dict())
        self.write_request()

    def arguments(self, command="prepare-work-product", **options):
        """Build complete command options without adding aliases, implicit bases or optional controls."""
        if command == "prepare-work-product":
            values = dict(config=self.config, checkout=self.destination, request=self.request_path,
                          destination=self.package)
        elif command == "inspect-proposal":
            values = dict(proposal=self.package)
        elif command == "submit-work-product":
            values = dict(config=self.config, proposal=self.package)
        else:
            return operations.CliOperationTests.arguments(self, command, **options)
        values.update(options)
        return [command, *(part for key, value in values.items() for part in ("--" + key.replace("_", "-"), str(value)))]

    def write_request(self):
        """Save explicit full metadata/provenance declarations as an owned private input file."""
        self.request_path.write_text(json.dumps(self.request_value), encoding="utf-8")
        self.request_path.chmod(0o600)

    def draft(self, destination=None, revision=1):
        """Create an exact historical draft through the actual CLI and return its selected path."""
        destination = destination or self.destination
        self.invoke(self.arguments("checkout-work-product", destination=destination, revision=revision))
        return destination

    def result(self, command, **options):
        """Decode a complete acknowledged CLI result, leaving failure assertions to individual tests."""
        return json.loads(self.invoke(self.arguments(command, **options)).stdout)["result"]

    def leaf_rename_prelude(self, boundary, retained, *, after_publication=False):
        """Inject a real proposal rename within its checked reader, optionally only after publication."""
        return f'''
from pathlib import Path
from research_pipeline import cli_controls, cli_proposals

selected = Path({str(self.package / "proposal.json")!r})
retained = Path({str(retained)!r})
original_read = cli_proposals.read_control
original_fault = cli_controls._fault
armed = {not after_publication!r}
fired = False

def arm(boundary):
    """Allow mutation only once the marker has been removed by real publication."""
    global armed
    if boundary == "published":
        armed = True

def rename(boundary):
    """Retain the observed proposal outside the package before the real remaining checks."""
    global fired
    if armed and not fired and boundary == {boundary!r}:
        fired = True
        selected.rename(retained)

def read_selected(parent, name, path, maximum, *, modes):
    """Scope mutation to the saved proposal; configuration and other leaves cannot trigger it."""
    if path != selected:
        return original_read(parent, name, path, maximum, modes=modes)
    cli_controls._fault = rename
    try:
        return original_read(parent, name, path, maximum, modes=modes)
    finally:
        cli_controls._fault = original_fault

cli_proposals.read_control = read_selected
cli_proposals._fault = arm
'''

    def test_full_edit_review_submit_history_and_original_receipt(self):
        """Safely permissioned selected files round-trip through review/submit, preserving canonical originals."""
        before = self.snapshot()
        self.draft()
        (self.destination / "notes/α.txt").write_bytes(b"Edited text\n")
        (self.destination / "extra").write_bytes(b"")
        (self.destination / "extra").chmod(0o600)
        (self.destination / "opaque").mkdir(mode=0o700)
        (self.destination / "opaque/private").write_bytes(b"unselected")
        self.request_value["selected_paths"] = ["empty", "notes/α.txt", "copy.txt", "extra"]
        self.request_value["metadata"]["title"] = "Edited title \x1b[31m α"
        self.request_value["record_provenance"]["actor"] = "editor"
        self.request_value["submission_provenance"]["details"] = {"explicit": "new attribution"}
        self.write_request()
        prepared = self.result("prepare-work-product")
        after = self.snapshot()
        self.assertEqual(before[0], after[0])
        for digest, data in before[1].items():
            self.assertEqual(after[1][digest], data)
        observed = self.result("inspect-proposal")
        changes = observed["summary"]["changes"]
        self.assertEqual(changes["new_files"], self.request_value["selected_paths"])
        self.assertEqual([entry["status"] for entry in changes["paths"]],
                         ["changed", "removed", "unchanged", "unchanged", "added"])
        self.assertEqual(set(changes["provenance_changes"]), {"record", "submission"})
        self.assertIn(dict(path="opaque", path_escaped=False, kind="directory", opaque=True),
                      changes["unselected_material"])
        self.assertEqual(observed["proposal_sha256"], prepared["proposal_sha256"])
        committed = self.result("submit-work-product")
        saved_receipt = self.result("inspect-receipt", submission_id="edited")["receipt"]
        self.assertEqual(committed["receipt"], saved_receipt)
        historical = self.result("inspect-record", revision=1)
        self.assertEqual(historical["envelope"], self.envelope.to_dict())
        new = self.result("inspect-record", revision=2)["envelope"]
        self.assertEqual(new, observed["proposal"]["submission"]["records"][0])
        self.assertEqual((self.destination / "notes/α.txt").read_bytes(), b"Edited text\n")
        self.assertEqual(self.result("submit-work-product")["receipt"], saved_receipt)

    def test_two_prepared_drafts_stale_submit_and_stale_prepare(self):
        """Independent edits prepared before a commit remain intact across distinct stale conflict paths."""
        first = self.draft()
        second = self.draft(self.parent / "second")
        (first / "copy.txt").write_bytes(b"first")
        (second / "copy.txt").write_bytes(b"second")
        self.result("prepare-work-product")
        self.request_value["submission_id"] = "competing"
        self.write_request()
        other = self.parent / "other-package"
        self.result("prepare-work-product", checkout=second, destination=other)
        self.result("submit-work-product")
        before = self.snapshot()[0]
        stale = self.invoke(self.arguments("submit-work-product", proposal=other), expected=4)
        self.assertIn("Saved submission conflicts", json.loads(stale.stderr)["message"])
        absent = self.parent / "stale-prepare"
        stale = self.invoke(self.arguments(destination=absent, checkout=second), expected=4)
        self.assertIn("Preparation conflicts", json.loads(stale.stderr)["message"])
        self.assertFalse(absent.exists())
        self.assertEqual(self.snapshot()[0], before)
        self.assertEqual((first / "copy.txt").read_bytes(), b"first")
        self.assertEqual((second / "copy.txt").read_bytes(), b"second")

    def test_observed_package_directory_races_are_conflicts(self):
        """Real candidate stat/rename races report conflict, retaining saved bytes/drafts and no submission."""
        self.draft()
        self.result("prepare-work-product")
        before = self.snapshot()
        documents = {str(path.relative_to(self.package)): path.read_bytes()
                     for path in self.package.rglob("*") if path.is_file()}
        draft_bytes = {str(path.relative_to(self.destination)): path.read_bytes()
                       for path in self.destination.rglob("*") if path.is_file()}
        for command in ("inspect-proposal", "submit-work-product"):
            for replacement in (False, True):
                with self.subTest(command=command, replacement=replacement):
                    retained = self.parent / f"retained-{command}-{replacement}"
                    prelude = f'''
from pathlib import Path
from research_pipeline import checkout

selected = Path({str(self.package)!r})
retained = Path({str(retained)!r})
real_stat = checkout._stat
fired = False

def raced_stat(parent, name):
    """Return a successful real initial observation, then detach its binding before the real open."""
    global fired
    observed = real_stat(parent, name)
    if name == selected.name and not fired:
        fired = True
        selected.rename(retained)
        if {replacement!r}:
            selected.mkdir(mode=0o700)
    return observed

checkout._stat = raced_stat
'''
                    result = self.invoke(self.arguments(command), prelude=prelude, expected=4)
                    diagnostic = self.diagnostic(result, "conflict")
                    self.assertEqual(diagnostic["message"],
                                     "Saved package bindings or contents changed during observation.")
                    self.assertTrue(retained.is_dir())  # The real rename proves the fault fired.
                    self.assertEqual({str(path.relative_to(retained)): path.read_bytes()
                                      for path in retained.rglob("*") if path.is_file()}, documents)
                    self.assertEqual(self.snapshot(), before)
                    receipt = self.invoke(self.arguments("inspect-receipt", submission_id="edited"), expected=3)
                    self.assertIsNone(json.loads(receipt.stdout)["result"]["receipt"])
                    self.assertEqual({str(path.relative_to(self.destination)): path.read_bytes()
                                      for path in self.destination.rglob("*") if path.is_file()}, draft_bytes)
                    if replacement:
                        self.assertEqual(list(self.package.iterdir()), [])
                        self.package.rmdir()
                    retained.rename(self.package)

    def test_observed_saved_leaf_disappearance_is_conflict(self):
        """Real CLI reads lose a proposal binding at both seams, retain all bytes and never submit."""
        self.draft()
        (self.destination / "copy.txt").write_bytes(b"retained draft edit")
        self.result("prepare-work-product")
        before = self.snapshot()
        documents = {str(path.relative_to(self.package)): path.read_bytes()
                     for path in self.package.rglob("*") if path.is_file()}
        draft_bytes = {str(path.relative_to(self.destination)): path.read_bytes()
                       for path in self.destination.rglob("*") if path.is_file()}
        for command in ("inspect-proposal", "submit-work-product"):
            for boundary in ("before_control_open", "after_control_read"):
                with self.subTest(command=command, boundary=boundary):
                    retained = self.parent / f"retained-{command}-{boundary}"
                    prelude = self.leaf_rename_prelude(boundary, retained)
                    result = self.invoke(self.arguments(command), prelude=prelude, expected=4)
                    diagnostic = self.diagnostic(result, "conflict")
                    self.assertEqual(diagnostic["message"],
                                     "Saved package bindings or contents changed during observation.")
                    self.assertFalse((self.package / "proposal.json").exists())
                    self.assertEqual(retained.read_bytes(), documents["proposal.json"])
                    self.assertEqual({str(path.relative_to(self.package)): path.read_bytes()
                                      for path in self.package.rglob("*") if path.is_file()},
                                     {name: data for name, data in documents.items() if name != "proposal.json"})
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual({str(path.relative_to(self.destination)): path.read_bytes()
                                      for path in self.destination.rglob("*") if path.is_file()}, draft_bytes)
                    receipt = self.invoke(self.arguments("inspect-receipt", submission_id="edited"), expected=3)
                    self.assertIsNone(json.loads(receipt.stdout)["result"]["receipt"])
                    # Explicit fixture reset between independent CLI observations.
                    retained.rename(self.package / "proposal.json")

    def test_postpublication_saved_leaf_disappearance_remains_uncertain(self):
        """Final verification losing a leaf after publication retains status 7 and never recreates a marker."""
        self.draft()
        self.result("prepare-work-product")
        documents = {str(path.relative_to(self.package)): path.read_bytes()
                     for path in self.package.rglob("*") if path.is_file()}
        before = self.snapshot()
        draft_bytes = {str(path.relative_to(self.destination)): path.read_bytes()
                       for path in self.destination.rglob("*") if path.is_file()}
        for boundary in ("before_control_open", "after_control_read"):
            with self.subTest(boundary=boundary):
                self.package = self.parent / ("published-" + boundary)
                retained = self.parent / ("retained-" + boundary)
                prelude = self.leaf_rename_prelude(boundary, retained, after_publication=True)
                result = self.invoke(self.arguments(), prelude=prelude, expected=7)
                self.diagnostic(result, "effects_uncertain")
                self.assertFalse((self.package / "proposal.json").exists())
                self.assertEqual(retained.read_bytes(), documents["proposal.json"])
                self.assertFalse((self.package / ".work-product-proposal/incomplete").exists())
                self.assertEqual({str(path.relative_to(self.package)): path.read_bytes()
                                  for path in self.package.rglob("*") if path.is_file()},
                                 {name: data for name, data in documents.items() if name != "proposal.json"})
                self.assertEqual(self.snapshot(), before)
                self.assertEqual({str(path.relative_to(self.destination)): path.read_bytes()
                                  for path in self.destination.rglob("*") if path.is_file()}, draft_bytes)
                receipt = self.invoke(self.arguments("inspect-receipt", submission_id="edited"), expected=3)
                self.assertIsNone(json.loads(receipt.stdout)["result"]["receipt"])

    def test_genuine_missing_package_inspection_and_submission(self):
        """Stable initial absence produces bounded null inspection/status 3 and never submits metadata."""
        before = self.snapshot()
        for path in (self.package, self.parent / "missing-parent" / "saved"):
            inspected = self.invoke(self.arguments("inspect-proposal", proposal=path), expected=3)
            self.assertEqual(inspected.stderr, b"")
            self.assertLess(len(inspected.stdout), 2048)
            value = json.loads(inspected.stdout)
            self.assertEqual(value["status"], "absent")
            self.assertEqual(value["result"], dict(destination=str(path), state="absent",
                             proposal_sha256=None, submission_id=None, base=None, proposed_revision=None,
                             proposal=None, summary=None, historical_durability="unknown"))
            submitted = self.invoke(self.arguments("submit-work-product", proposal=path), expected=3)
            self.diagnostic(submitted, "missing")
            self.assertEqual(self.snapshot(), before)
            receipt = self.invoke(self.arguments("inspect-receipt", submission_id="edited"), expected=3)
            self.assertIsNone(json.loads(receipt.stdout)["result"]["receipt"])

    def test_same_id_different_saved_requests_conflict(self):
        """Two previews may share an unused ID, but only identical saved requests reconcile after commit."""
        self.draft()
        self.result("prepare-work-product")
        (self.destination / "copy.txt").write_bytes(b"different")
        second = self.parent / "different"
        self.result("prepare-work-product", destination=second)
        receipt = self.result("submit-work-product")["receipt"]
        self.invoke(self.arguments("submit-work-product", proposal=second), expected=4)
        self.assertEqual(self.result("submit-work-product")["receipt"], receipt)

    def test_retry_after_advance_draft_deletion_and_object_loss(self):
        """Original-ID reconciliation precedes current heads and artifact availability after later commits."""
        self.draft()
        (self.destination / "copy.txt").write_bytes(b"revision two")
        self.result("prepare-work-product")
        receipt = self.result("submit-work-product")["receipt"]
        later_draft = self.draft(self.parent / "later", revision=2)
        self.request_value.update(base={**self.base.to_dict(), "revision": 2}, expected_head=2, submission_id="third")
        self.write_request()
        (later_draft / "copy.txt").write_bytes(b"revision three")
        later_package = self.parent / "third-package"
        self.result("prepare-work-product", checkout=later_draft, destination=later_package)
        self.result("submit-work-product", proposal=later_package)
        shutil.rmtree(self.destination)
        shutil.rmtree(later_draft)
        for index, path in enumerate((self.root / "objects").iterdir()):
            if index % 2:
                path.chmod(0o600)
                path.write_bytes(b"damaged")
                path.chmod(0o400)
            else:
                path.unlink()
        before = self.snapshot()[0]
        self.assertEqual(self.result("submit-work-product")["receipt"], receipt)
        self.assertEqual(self.result("inspect-receipt", submission_id="edited")["receipt"], receipt)
        self.assertEqual(self.snapshot()[0], before)

    def test_new_request_missing_objects_never_commits(self):
        """A new saved request still undergoes object admission and cannot commit unavailable bytes."""
        self.draft()
        self.result("prepare-work-product")
        before = self.snapshot()[0]
        (self.root / "objects" / self.a.digest).unlink()
        result = self.invoke(self.arguments("submit-work-product"), expected=6)
        self.diagnostic(result, "integrity_error")
        self.assertEqual(self.snapshot()[0], before)
        self.assertEqual(self.result("inspect-receipt", submission_id="submit")["receipt"],
                         self.store.get_submission("submit").to_dict())

    def test_ordering_only_changes_and_explicit_limits(self):
        """Reordered equal bytes remain visible, while declared inventory and output bounds prevent commit."""
        self.draft()
        self.request_value["selected_paths"].reverse()
        self.write_request()
        before = self.snapshot()[0]
        self.invoke(self.arguments(max_output_bytes=1), expected=5)
        self.assertFalse(self.package.exists())
        self.result("prepare-work-product")
        observation = self.result("inspect-proposal")
        changes = observation["summary"]["changes"]
        self.assertNotEqual(changes["old_files"], changes["new_files"])
        self.assertTrue(all(entry["status"] == "unchanged" for entry in changes["paths"]))
        for options in (dict(max_files=3), dict(max_file_bytes=0), dict(max_total_bytes=0), dict(max_output_bytes=1)):
            self.invoke(self.arguments("submit-work-product", **options), expected=5)
        self.assertEqual(self.snapshot()[0], before)

    def test_usage_and_malformed_request_have_no_dependent_writes(self):
        """Every new parser rejects repeated/abbreviated options, and malformed metadata precedes draft reads."""
        before = self.snapshot()
        for command in ("prepare-work-product", "inspect-proposal", "submit-work-product"):
            self.invoke([command, "--help"])
            arguments = self.arguments(command)
            self.invoke(arguments + ["--max-output", "100"], expected=2)
            self.invoke(arguments + ["--max-output-bytes", "1", "--max-output-bytes", "2"], expected=2)
        self.request_value["metadata"]["unknown"] = 1
        self.write_request()
        self.invoke(self.arguments(), expected=5)
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.package.exists())
        self.assertEqual(self.snapshot(), before)

    def test_offline_inspection_has_no_store_or_write_access(self):
        """Offline package inspection reads only the selected ancestors/leaves and never synchronizes."""
        self.draft()
        self.result("prepare-work-product")
        prelude = '''
import os
from research_pipeline import cli_proposals, store

def denied(*args, **kwargs):
    """Fail if offline inspection tries to access canonical storage or perform a durability barrier."""
    raise AssertionError("unexpected store or sync")
store.RecordStore.open = denied
os.fsync = denied
'''
        self.invoke(self.arguments("inspect-proposal"), prelude=prelude)
        self.store.close()
        shutil.rmtree(self.root)
        self.result("inspect-proposal")
        self.invoke(self.arguments("submit-work-product"), expected=3)
        self.assertFalse(self.root.exists())

    def test_saved_package_cannot_be_writable_parent(self):
        """The new sentinel excludes checkout and preparation destinations even with otherwise private modes."""
        self.draft()
        self.result("prepare-work-product")
        self.invoke(self.arguments("checkout-work-product", destination=self.package / "draft"), expected=5)
        self.invoke(self.arguments(destination=self.package / "nested"), expected=5)
        self.invoke(self.arguments(checkout=self.package, destination=self.parent / "other"), expected=5)
        self.assertEqual(set(path.name for path in self.package.iterdir()),
                         {"proposal.json", "summary.json", ".work-product-proposal"})

    def test_real_termination_retained_publication_states(self):
        """Actual process exits leave early, partial, complete-unpublished and published evidence inspectable."""
        self.draft()
        for boundary, state in (("reserved", "incomplete"), ("marked", "incomplete"),
                                ("wrote_proposal.json", "incomplete"),
                                ("before_publish", "complete_unpublished"), ("published", "published")):
            destination = self.parent / boundary
            prelude = f'''
import os
from research_pipeline import cli_proposals

def stop(boundary):
    """Terminate after a real lifecycle boundary, without exception unwinding or cleanup."""
    if boundary == {boundary!r}:
        os._exit(91)
cli_proposals._fault = stop
'''
            self.invoke(self.arguments(destination=destination), prelude=prelude, expected=91)
            observed = self.result("inspect-proposal", proposal=destination)
            self.assertEqual(observed["state"], state)
            if state != "published":
                self.invoke(self.arguments("submit-work-product", proposal=destination), expected=5)
                self.assertEqual(self.result("inspect-proposal", proposal=destination), observed)

    def test_real_store_interruptions_and_original_id_reconciliation(self):
        """Real transaction exits roll back before commit and preserve the original receipt after commit."""
        self.draft()
        self.result("prepare-work-product")
        before = self.snapshot()[0]
        for boundary in ("before_metadata", "after_first_revision", "after_commit"):
            prelude = f'''
import os
from research_pipeline import store

def stop(boundary):
    """Exit at the established store transaction seam without allowing normal close or acknowledgment."""
    if boundary == {boundary!r}:
        os._exit(92)
store._fault = stop
'''
            self.invoke(self.arguments("submit-work-product"), prelude=prelude, expected=92)
            if boundary != "after_commit":
                absent = self.invoke(self.arguments("inspect-receipt", submission_id="edited"), expected=3)
                self.assertIsNone(json.loads(absent.stdout)["result"]["receipt"])
                self.assertEqual(self.snapshot()[0], before)
        original = self.result("inspect-receipt", submission_id="edited")["receipt"]
        self.assertEqual(self.result("submit-work-product")["receipt"], original)

    def test_reportable_submit_interrupt_and_input_close_failure(self):
        """Input close prevents commit; an interruption after entering submit reports original-ID uncertainty."""
        self.draft()
        self.result("prepare-work-product")
        before = self.snapshot()[0]
        prelude = '''
from research_pipeline import store

def interrupt(boundary):
    """Interrupt a real transaction before metadata, requiring conservative CLI uncertainty."""
    if boundary == "before_metadata":
        raise KeyboardInterrupt()
store._fault = interrupt
'''
        failure = self.invoke(self.arguments("submit-work-product"), prelude=prelude, expected=7)
        context = json.loads(failure.stderr)["context"]
        self.assertEqual(context["submission_id"], "edited")
        self.assertIn("inspect-receipt", context["next_action"])
        self.assertEqual(self.snapshot()[0], before)
        prelude = '''
import os
from research_pipeline import cli_proposals
original_close = os.close
armed = False

def arm(boundary):
    """Arm only after saved-input synchronization, before the actual final resource closes."""
    global armed
    if boundary == "after_input_sync":
        armed = True

def close(fd):
    """Close the actual descriptor then report failure, preventing entry into canonical submit."""
    original_close(fd)
    if armed:
        raise OSError("input close failed")
cli_proposals._fault = arm
os.close = close
'''
        self.invoke(self.arguments("submit-work-product"), prelude=prelude, expected=6)
        self.assertEqual(self.snapshot()[0], before)

    def test_output_short_partial_flush_close_and_broken_pipe(self):
        """Every new command distinguishes failed output acknowledgment, including a committed lost receipt."""
        self.draft()
        self.result("prepare-work-product")
        for command in ("inspect-proposal", "prepare-work-product", "submit-work-product"):
            for failure in ("short", "partial", "flush", "close", "broken"):
                options = {"destination": self.parent / (command + failure)} if command == "prepare-work-product" else {}
                prelude = f'''
import os
import sys
original = sys.stdout
failure = {failure!r}

class Output:
    """Forward actual bytes with deterministic short writes or late acknowledgment failures."""
    buffer = None
    def __init__(self):
        """Expose the same object as its byte stream and remember whether partial bytes escaped."""
        self.buffer = self
        self.wrote = False
    def fileno(self):
        """Retain the physical stdout descriptor for failure silencing."""
        return original.fileno()
    def write(self, data):
        """Forward actual short bytes or report a deterministic recipient failure."""
        if failure == "broken" or (failure == "partial" and self.wrote):
            raise BrokenPipeError()
        self.wrote = True
        return os.write(original.fileno(), data[:7] if failure in ("short", "partial") else data)
    def flush(self):
        """Fail only after physical bytes were delivered when testing flush acknowledgment."""
        if failure == "flush":
            raise OSError("flush")
        original.flush()
    def close(self):
        """Fail the close acknowledgment without claiming previously delivered bytes were rolled back."""
        if failure == "close":
            raise OSError("close")
        original.close()
sys.stdout = Output()
'''
                status = 0 if failure == "short" else 6 if command == "inspect-proposal" else 7
                process = self.invoke(self.arguments(command, **options), prelude=prelude, expected=status)
                if failure == "partial":
                    self.assertEqual(len(process.stdout), 7)
                if status:
                    context = json.loads(process.stderr)["context"]
                    self.assertIn("inspect-receipt" if command == "submit-work-product" else
                                  "inspect-proposal" if command == "prepare-work-product" else "Repeat",
                                  context["next_action"])
                if command == "submit-work-product":
                    receipt = self.result("inspect-receipt", submission_id="edited")["receipt"]
                    self.assertEqual(self.result("submit-work-product")["receipt"], receipt)

    def test_partial_payload_process_exit_is_invalid_retained_evidence(self):
        """A process exit mid-payload preserves malformed available JSON and never presents it as ordinary incomplete."""
        self.draft()
        prelude = '''
import os
from research_pipeline import checkout

def partial(fd, data):
    """Write a real prefix of the first package payload, then terminate without cleanup."""
    os.write(fd, data[:17])
    os._exit(93)
checkout._write_all = partial
'''
        self.invoke(self.arguments(), prelude=prelude, expected=93)
        self.assertEqual((self.package / "proposal.json").stat().st_size, 17)
        self.assertTrue((self.package / ".work-product-proposal/incomplete").exists())
        before = self.snapshot()[0]
        self.invoke(self.arguments("inspect-proposal"), expected=5)
        self.invoke(self.arguments("submit-work-product"), expected=5)
        self.assertEqual(self.snapshot()[0], before)

    def test_physical_closed_stdout_reader_after_commit(self):
        """A physically closed pipe loses commit acknowledgment while the original ID remains reconcilable."""
        import subprocess
        import sys
        self.draft()
        self.result("prepare-work-product")
        reader, writer = os.pipe()
        os.close(reader)
        try:
            process = subprocess.Popen([sys.executable, "-B", "-m", "research_pipeline",
                                        *self.arguments("submit-work-product")], cwd=self.parent,
                                       env={**os.environ, "PYTHONPATH": str(operations.SRC),
                                            "PYTHONDONTWRITEBYTECODE": "1"},
                                       stdout=writer, stderr=subprocess.PIPE)
        finally:
            os.close(writer)
        _, diagnostic = process.communicate(timeout=40)
        self.assertEqual(process.returncode, 7, diagnostic)
        context = json.loads(diagnostic)["context"]
        self.assertEqual(context["submission_id"], "edited")
        receipt = self.result("inspect-receipt", submission_id="edited")["receipt"]
        self.assertEqual(self.result("submit-work-product")["receipt"], receipt)
