"""Real Tool CLI private-control, SQLite contention, process-loss and stdout acknowledgement faults."""

import errno
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from tests.test_vault import child_environment
from tests.tool_cli_fixtures import ToolCliCase
from tests.tool_registration_fixtures import rows


class ToolCliFilesystemTests(ToolCliCase):
    """Exercise owned no-follow input observations with actual private leaves and directory mutations."""

    def test_initial_missing_controls_runtime_and_incomplete_layout(self):
        """Initial config absence is invalid input, explicit batch/runtime absence is missing, and no runtime is created."""
        self.failure(5, argv=self.args(config=self.parent / "missing-config"), code="invalid_input")
        self.failure(3, argv=self.args(batch=self.parent / "missing-batch"), code="missing")
        missing = self.parent / "missing-runtime"
        self.save(self.config, {**self.config_value, "store": str(missing)})
        self.failure(3, code="missing")
        self.assertFalse(missing.exists())
        missing.mkdir(mode=0o700)
        self.failure(5, code="unsafe_layout")

    def test_control_modes_links_fifo_parent_symlink_and_modes(self):
        """Both controls require single regular private leaves and exact owned 0700 parents before any read."""
        before = rows(self.root)
        for option, selected in (("config", self.config), ("batch", self.batch)):
            data = selected.read_bytes()
            for mode in (0o644, 0o666, 0o000):
                selected.chmod(mode)
                self.failure(5, code="unsafe_layout")
                selected.chmod(0o600)
            link = self.parent / (option + "-hard")
            os.link(selected, link)
            self.failure(5, code="unsafe_layout")
            link.unlink()
            selected.unlink()
            selected.symlink_to(link)
            self.failure(5, code="unsafe_layout")
            selected.unlink()
            os.mkfifo(selected, 0o600)
            self.failure(5, code="unsafe_layout")
            selected.unlink()
            selected.write_bytes(data)
            selected.chmod(0o600)
        alias = self.parent / "alias"
        alias.symlink_to(self.parent, target_is_directory=True)
        self.failure(5, argv=self.args(config=alias / self.config.name), code="unsafe_layout")
        self.parent.chmod(0o750)
        try:
            self.failure(5, code="unsafe_layout")
        finally:
            self.parent.chmod(0o700)
        self.assertEqual(rows(self.root), before)

    def test_leaf_mutation_at_open_read_and_final_observations(self):
        """Growth, truncation, same-size replacement and disappearance retain established integrity meaning."""
        before = rows(self.root)
        for leaf in (self.config, self.batch):
            original = leaf.read_bytes()
            for boundary in ("before_control_open", "after_control_read"):
                for mutation in ("growth", "truncate", "replace", "disappear"):
                    prelude = f'''
from pathlib import Path
from research_pipeline import cli_controls
selected = Path({str(leaf)!r})
real = cli_controls.read_control
fired = False

def mutate(boundary):
    """Mutate the actual selected leaf once within its no-follow checked read."""
    global fired
    if fired or boundary != {boundary!r}:
        return
    fired = True
    mutation = {mutation!r}
    if mutation == "growth":
        with selected.open("ab") as stream:
            stream.write(b" ")
    elif mutation == "truncate":
        selected.write_bytes(b"")
    elif mutation == "replace":
        data = selected.read_bytes()
        selected.unlink()
        selected.write_bytes(data)
        selected.chmod(0o600)
    else:
        selected.unlink()

def read(parent, name, path, maximum, *, modes):
    """Scope the real reader's fault to only the selected control, keeping config/batch independent."""
    original = cli_controls._fault
    if path == selected:
        cli_controls._fault = mutate
    try:
        return real(parent, name, path, maximum, modes=modes)
    finally:
        cli_controls._fault = original
cli_controls.read_control = read
'''
                    self.failure(6, prelude=prelude, code="integrity_error")
                    leaf.write_bytes(original)
                    leaf.chmod(0o600)
                    self.assertEqual(rows(self.root), before)

    def test_detached_earlier_ancestor_when_later_component_missing(self):
        """A missing next directory cannot hide replacement of a previously pinned ancestor."""
        control_parent = self.parent / "controls"
        control_parent.mkdir(mode=0o700)
        config = control_parent / "config.json"
        self.save(config, self.config_value)
        held = self.parent / "held-controls"
        absent = control_parent / "missing" / "batch.json"
        prelude = f'''
from pathlib import Path
from research_pipeline.cli_controls import _ObservedDirectories
real = _ObservedDirectories.open
selected = Path({str(control_parent)!r})
fired = False

def open_directory(self, name, parent=None, *, private=False, exact=False, path=None):
    """Detach an earlier held control directory just before a later missing component acquisition."""
    global fired
    if not fired and str(path) == str(selected / "missing"):
        fired = True
        selected.rename(Path({str(held)!r}))
        selected.mkdir(mode=0o700)
    return real(self, name, parent, private=private, exact=exact, path=path)
_ObservedDirectories.open = open_directory
'''
        self.failure(6, argv=self.args(config=config, batch=absent), prelude=prelude, code="integrity_error")
        self.assertIsNone(self.store.get_submission(self.saved.submission_id))

    def test_postcommit_control_and_ancestor_mutations_are_uncertain(self):
        """Final held checks after actual COMMIT retain original ID and committed metadata."""
        for mode in ("leaf", "ancestor"):
            if mode == "ancestor":
                from research_pipeline.domain import RecordEnvelope, Submission
                self.saved = Submission("ancestor-original", self.saved.provenance,
                    [RecordEnvelope.from_dict({**item.to_dict(), "revision": 2}) for item in self.saved.records],
                    {"assessment": 1, "tool": 1})
            self.write_batch()
            self.save(self.config, self.config_value)
            prelude = f'''
from pathlib import Path
from research_pipeline import store
selected = Path({str(self.batch)!r})

def mutate(boundary):
    """Mutate the actual saved control after durable metadata commit, before receipt return."""
    if boundary != "after_commit":
        return
    if {mode!r} == "leaf":
        selected.unlink()
    else:
        parent = selected.parent
        parent.rename(parent.with_name(parent.name + "-detached"))
        parent.mkdir(mode=0o700)
store._fault = mutate
'''
            diagnostic = self.failure(7, prelude=prelude, code="effects_uncertain")
            self.assertEqual(diagnostic["context"]["submission_id"], self.saved.submission_id)
            self.assertIn("inspect-receipt", diagnostic["context"]["next_action"])
            if mode == "ancestor":
                self.parent.rmdir()
                self.parent.with_name(self.parent.name + "-detached").rename(self.parent)
            self.assertIsNotNone(self.store.get_submission(self.saved.submission_id))
            self.assertEqual(len(self.store.audit_events()), 1 if mode == "leaf" else 2)
            self.write_batch()
            self.assertEqual(self.result()["receipt"], self.store.get_submission(self.saved.submission_id).to_dict())

    def test_checked_input_and_held_directory_close_failures(self):
        """A real closed input/held descriptor with failed acknowledgement cannot become success."""
        before = rows(self.root)
        prelude = f'''
import errno, os
from research_pipeline import cli_controls
real = os.close
armed = False

def mark(boundary):
    """Arm only after the real first input read, immediately before its checked close."""
    global armed
    if boundary == "after_control_read":
        armed = True

def close(fd):
    """Close the actual descriptor once then expose an EIO acknowledgement failure."""
    global armed
    real(fd)
    if armed:
        armed = False
        raise OSError(errno.EIO, "checked input close")
cli_controls._fault = mark
os.close = close
'''
        self.failure(6, prelude=prelude, code="operational_error")
        self.assertEqual(rows(self.root), before)
        prelude = '''
import errno, os, stat
from research_pipeline.store import RecordStore
real_submit = RecordStore.submit_typed
real_close = os.close
armed = False

def submit(self, request):
    """Arm close-loss only after real submission has durably returned its receipt."""
    global armed
    receipt = real_submit(self, request)
    armed = True
    return receipt

def close(fd):
    """Close a real held directory descriptor before reporting its lost acknowledgement."""
    global armed
    directory = stat.S_ISDIR(os.fstat(fd).st_mode)
    real_close(fd)
    if armed and directory:
        armed = False
        raise OSError(errno.EIO, "held directory close")
RecordStore.submit_typed = submit
os.close = close
'''
        self.failure(7, prelude=prelude, code="effects_uncertain")
        self.assertEqual(len(self.store.audit_events()), 1)

    def test_source_exclusions_control_overlap_and_recognizable_ancestors(self):
        """Bidirectional exclusions and fixed sentinels refuse layouts without changing runtime or protected trees."""
        source = Path(__file__).resolve().parents[2]
        before = rows(self.root)
        for root in (source, source / "nested", source.parent):
            self.save(self.config, {**self.config_value, "store": str(root)})
            self.failure(5, code="unsafe_layout")
        for root in (self.root, self.parent):
            self.save(self.config, {**self.config_value, "protected_roots": [str(root)]})
            self.failure(5, code="unsafe_layout")
        self.save(self.config, self.config_value)
        self.failure(5, argv=self.args(batch=self.config), code="unsafe_layout")
        for marker in ("snapshot.sqlite3", ".backup-incomplete", ".work-product", "manifest.json", "refresh.json", ".work-product-proposal"):
            selected = self.parent / marker
            selected.write_bytes(b"must not be opened")
            selected.chmod(0o000)
            try:
                self.failure(5, code="unsafe_layout")
            finally:
                selected.unlink()
        self.assertEqual(rows(self.root), before)

    def test_real_errno_at_control_and_runtime_boundaries(self):
        """OS failures retain EACCES/EIO rather than being mislabeled as missing or invalid authored content."""
        for selected in (self.config.name, "runtime"):
            for number in (errno.EACCES, errno.EIO):
                prelude = f'''
import os
real = os.stat

def stat(path, *args, **kwargs):
    """Wrap a real stat boundary with the actual OS errno shape used by acquisition failures."""
    if str(path) == {selected!r}:
        raise OSError({number}, "injected OS boundary", path)
    return real(path, *args, **kwargs)
os.stat = stat
'''
                self.failure(6, prelude=prelude, code="operational_error")


class ToolCliRecoveryTests(ToolCliCase):
    """Keep physical commit effects separate from acknowledgements and original-ID recovery."""

    def test_actual_busy_writer_and_before_entry_busy_classification(self):
        """An independent SQLite writer lock produces real five-second busy refusal, with no new metadata."""
        before = rows(self.root)
        with sqlite3.connect(self.root / "metadata.sqlite3") as lock:
            lock.execute("BEGIN IMMEDIATE")
            diagnostic = self.failure(7, code="effects_uncertain")
            self.assertEqual(diagnostic["context"]["submission_id"], self.saved.submission_id)
            lock.rollback()
        self.assertEqual(rows(self.root), before)
        with sqlite3.connect(self.root / "metadata.sqlite3") as lock:
            lock.execute("BEGIN EXCLUSIVE")
            self.failure(6, code="operational_error")
            lock.rollback()
        self.assertEqual(rows(self.root), before)

    def test_actual_process_exit_after_commit_then_receipt_and_identical_retry(self):
        """A real child exits without cleanup after COMMIT; reopen recovers one original event and receipt."""
        prelude = '''
import os
from research_pipeline import store

def die(boundary):
    """Terminate at the existing real post-COMMIT seam without emitting a diagnostic or receipt."""
    if boundary == "after_commit":
        os._exit(83)
store._fault = die
'''
        result = self.invoke(prelude=prelude, expected=83)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")
        observed = self.invoke(["inspect-receipt", "--config", str(self.config), "--submission-id", self.saved.submission_id])
        receipt = json.loads(observed.stdout)["result"]["receipt"]
        before = rows(self.root)
        self.assertEqual(self.result()["receipt"], receipt)
        self.assertEqual(rows(self.root), before)
        self.assertEqual(len(self.store.audit_events()), 1)
        self.assertEqual(len(before["submissions"]), 1)

    def test_actual_metadata_fault_rolls_back_but_reports_unknown_entry_effects(self):
        """I/O-shaped interruption inside the real transaction is conservative; table observations prove rollback."""
        before = rows(self.root)
        prelude = '''
import errno
from research_pipeline import store

def fail(boundary):
    """Interrupt a real inserted revision before COMMIT, allowing the existing rollback path."""
    if boundary == "after_first_revision":
        raise OSError(errno.EIO, "metadata boundary")
store._fault = fail
'''
        self.failure(7, prelude=prelude, code="effects_uncertain")
        self.assertEqual(rows(self.root), before)
        self.assertIsNone(self.store.get_submission(self.saved.submission_id))
        self.result()

    def test_stdout_short_write_write_flush_close_and_physical_closed_reader(self):
        """Short writes drain; loss at each acknowledgement boundary preserves committed receipts without success claims."""
        self.result()
        for command in ("inspect-tool-record", "submit-tool-records"):
            for fault in ("short", "write", "partial", "flush", "close"):
                prelude = f'''
import os, sys
original = sys.stdout
fault = {fault!r}

class Output:
    """Forward physical stdout bytes and expose one deterministic acknowledgement fault."""
    def __init__(self):
        """Present the byte-stream interface used by the existing CLI emitter."""
        self.buffer = self
        self.wrote = False
    def fileno(self):
        """Retain the actual stdout descriptor for the emitter's failure silencing."""
        return original.fileno()
    def write(self, data):
        """Write real prefixes or fail before/after one real prefix."""
        if fault == "write" or (fault == "partial" and self.wrote):
            raise BrokenPipeError()
        self.wrote = True
        return os.write(original.fileno(), data[:7] if fault in ("short", "partial") else data)
    def flush(self):
        """Report late flush loss after physical bytes have already escaped."""
        if fault == "flush":
            raise OSError("flush")
        original.flush()
    def close(self):
        """Report close acknowledgement loss independently of previous physical writes."""
        if fault == "close":
            raise OSError("close")
        original.close()
sys.stdout = Output()
'''
                status = 0 if fault == "short" else 7 if command == "submit-tool-records" else 6
                process = self.invoke(self.args(command), expected=status, prelude=prelude)
                if status:
                    diagnostic = json.loads(process.stderr)
                    self.assertEqual(diagnostic["code"], "output_failed")
                    self.assertIn("inspect-receipt" if command == "submit-tool-records" else "discard partial output", diagnostic["context"]["next_action"])
                    if fault == "partial":
                        self.assertEqual(len(process.stdout), 7)
                else:
                    json.loads(process.stdout)
            reader, writer = os.pipe()
            os.close(reader)
            try:
                process = subprocess.Popen([sys.executable, "-B", "-m", "research_pipeline", *self.args(command)],
                    cwd=self.parent, env=child_environment(), stdout=writer, stderr=subprocess.PIPE)
            finally:
                os.close(writer)
            _, diagnostic = process.communicate(timeout=45)
            self.assertEqual(process.returncode, 7 if command == "submit-tool-records" else 6, diagnostic)
            self.assertEqual(json.loads(diagnostic)["code"], "output_failed")
        self.assertEqual(len(self.store.audit_events()), 1)
        self.assertEqual(self.result()["receipt"], self.store.get_submission(self.saved.submission_id).to_dict())
