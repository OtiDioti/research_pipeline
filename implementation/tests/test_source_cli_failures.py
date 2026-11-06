"""Held Source observations, real errno, transaction loss and checked stdout acknowledgement."""

import errno
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from tests.source_cli_fixtures import SourceCliCase
from tests.test_source_cli_controls import COMMANDS
from tests.test_vault import child_environment
from tests.tool_registration_fixtures import rows


class SourceCliFilesystemTests(SourceCliCase):
    """Exercise deterministic faults at actual control, store and descriptor lifecycle boundaries."""

    def test_control_mutations_open_read_and_final_gate(self):
        """Established leaves cannot disappear, grow, truncate or be replaced without integrity failure."""
        before = rows(self.root)
        for selected in (self.config, self.proposal):
            frozen = selected.read_bytes()
            for boundary in ('before_control_open', 'after_control_read'):
                for mutation in ('growth', 'truncate', 'replace', 'disappear'):
                    prelude = f'''
from pathlib import Path
from research_pipeline import cli_controls
selected = Path({str(selected)!r})
real = cli_controls.read_control
fired = False
active = False

def fault(boundary):
    """Mutate one actual observed leaf at its selected open/read gate."""
    global fired
    if not active or fired or boundary != {boundary!r}:
        return
    fired = True
    data = selected.read_bytes()
    mutation = {mutation!r}
    if mutation == 'growth':
        selected.write_bytes(data + b' ')
    elif mutation == 'truncate':
        selected.write_bytes(data[:-1])
    elif mutation == 'replace':
        replacement = selected.with_name('replacement')
        replacement.write_bytes(data)
        replacement.chmod(0o600)
        replacement.replace(selected)
    else:
        selected.unlink()

def read(parent, name, path, *args, **kwargs):
    """Arm the existing fault seam only for the selected control's bounded read."""
    global active
    active = path == selected
    return real(parent, name, path, *args, **kwargs)
cli_controls._fault = fault
cli_controls.read_control = read
'''
                    self.failure(6, code='integrity_error', prelude=prelude)
                    selected.write_bytes(frozen)
                    selected.chmod(0o600)
        prelude = f'''
from pathlib import Path
from research_pipeline import cli_source
real = cli_source._output

def output(*args, **kwargs):
    """Change an input after successful decoding, before final held observations."""
    result = real(*args, **kwargs)
    with Path({str(self.proposal)!r}).open('ab') as stream:
        stream.write(b' ')
    return result
cli_source._output = output
'''
        self.failure(6, code='integrity_error', prelude=prelude)
        self.assertEqual(rows(self.root), before)

    def test_earlier_observations_survive_later_missing_acquisition(self):
        """Missing proposal/runtime components do not mask mutation of earlier pinned controls/directories."""
        config = self.config.read_bytes()
        prelude = f'''
from pathlib import Path
from research_pipeline import cli_controls
real = cli_controls.read_observed_control

def read(*args, **kwargs):
    """Detach an earlier config only after its initial bounded read has completed."""
    result = real(*args, **kwargs)
    if args[2] == Path({str(self.config)!r}):
        Path({str(self.config)!r}).unlink()
    return result
cli_controls.read_observed_control = read
'''
        self.failure(6, argv=self.args(proposal=self.parent / 'missing'), code='integrity_error', prelude=prelude)
        self.config.write_bytes(config)
        self.config.chmod(0o600)
        self.save(self.config, {**self.config_value, 'store': str(self.parent / 'absent-runtime')})
        prelude = f'''
import os
from pathlib import Path
from research_pipeline import cli_source
real = cli_source.decode_proposal

def decode(*args, **kwargs):
    """Change an established parent before runtime traversal fails on a later component."""
    result = real(*args, **kwargs)
    os.chmod({str(self.parent)!r}, 0o750)
    return result
cli_source.decode_proposal = decode
'''
        try:
            self.failure(6, argv=self.args('submit-source-capture'), code='integrity_error', prelude=prelude)
        finally:
            self.parent.chmod(0o700)

    def test_initial_vs_late_directory_uid_gid_and_permitted_mode_changes(self):
        """Safety is established only after initial checks; even a permitted later tuple is corruption."""
        for probe in ('stat', 'fstat'):
            for field, offset in (('uid', 4), ('gid', 5), ('mode', 0)):
                prelude = f'''
import os, stat
from research_pipeline import cli_source
real_probe = os.{probe}
real_output = cli_source._output
active = False
selected = os.stat({str(self.parent)!r})

def probe(*args, **kwargs):
    """Change only selected-directory observed safety fields while retaining identity."""
    value = real_probe(*args, **kwargs)
    if active and (value.st_dev, value.st_ino) == (selected.st_dev, selected.st_ino):
        fields = list(value)
        fields[{offset}] = (stat.S_IFDIR | 0o750) if {field!r} == 'mode' else fields[{offset}] + 1
        return os.stat_result(fields)
    return value

def output(*args, **kwargs):
    """Arm observed changes after controls have established their original private safety."""
    global active
    result = real_output(*args, **kwargs)
    active = True
    return result
os.{probe} = probe
cli_source._output = output
'''
                self.failure(6, code='integrity_error', prelude=prelude)
        # Runtime root privacy is non-exact: 0750 remains permitted by its
        # initial rule, but changing the established 0700 tuple is still late.
        prelude = f'''
import os
from research_pipeline.store import RecordStore
real = RecordStore.submit_typed

def submit(self, request):
    """Change established runtime permissions after the actual canonical commit."""
    receipt = real(self, request)
    os.chmod({str(self.root)!r}, 0o750)
    return receipt
RecordStore.submit_typed = submit
'''
        try:
            self.failure(7, argv=self.args('submit-source-capture'), code='effects_uncertain', prelude=prelude)
        finally:
            self.root.chmod(0o700)
        self.assertIsNotNone(self.store.get_submission(self.saved.submission_id))

    def test_real_errno_at_open_read_reobservation_and_checked_close(self):
        """Real EACCES/EIO causes remain operational before entry, including wrapped integrity errors."""
        for number in (errno.EACCES, errno.EIO):
            for operation in ('open', 'read', 'reobserve', 'close'):
                prelude = f'''
import errno, os
from research_pipeline import cli_controls, cli_source
real_open, real_read, real_close = os.open, os.read, os.close
active = False
selected_fd = None

def mark(boundary):
    """Arm reobservation/close failures only after a successful initial read."""
    global active
    if boundary == 'after_control_read':
        active = True

def open(path, *args, **kwargs):
    """Fail only the actual selected private config open."""
    global selected_fd
    if str(path) == {self.config.name!r}:
        if {operation!r} == 'open':
            raise OSError({number}, 'open seam')
        selected_fd = real_open(path, *args, **kwargs)
        return selected_fd
    return real_open(path, *args, **kwargs)

def read(fd, *args):
    """Fail the selected bounded input read with a substantive errno."""
    if fd == selected_fd and {operation!r} == 'read':
        raise OSError({number}, 'read seam')
    return real_read(fd, *args)

def close(fd):
    """Close the actual input before reporting its lost close acknowledgement."""
    result = real_close(fd)
    if fd == selected_fd and active and {operation!r} == 'close':
        raise OSError({number}, 'close seam')
    return result
real_check = cli_source._check

def check(*args):
    """Expose an integrity wrapper with a real I/O cause at final reobservation."""
    if active and {operation!r} == 'reobserve':
        try:
            raise OSError({number}, 'reobservation seam')
        except OSError as error:
            from research_pipeline.checkout import CheckoutIntegrityError
            raise CheckoutIntegrityError('wrapper') from error
    return real_check(*args)
cli_controls._fault = mark
cli_source._check = check
os.open, os.read, os.close = open, read, close
'''
                self.failure(6, code='operational_error', prelude=prelude)

    def test_store_and_held_directory_close_failures_after_return(self):
        """Post-return close failures remain uncertain even when the actual commit is independently visible."""
        for target in ('store', 'directory'):
            prelude = f'''
import errno, os, stat
from research_pipeline.store import RecordStore
real_submit, real_store_close, real_close = RecordStore.submit_typed, RecordStore.close, os.close
active = False

def submit(self, request):
    """Arm acknowledgement loss after the real store returns a receipt."""
    global active
    result = real_submit(self, request)
    active = True
    return result

def store_close(self):
    """Close the actual store before exposing failed close acknowledgement."""
    real_store_close(self)
    if active and {target!r} == 'store':
        raise OSError(errno.EIO, 'store close')

def close(fd):
    """Close a real held descriptor before reporting the first directory-close failure."""
    global active
    directory = stat.S_ISDIR(os.fstat(fd).st_mode)
    result = real_close(fd)
    if active and directory and {target!r} == 'directory':
        active = False
        raise OSError(errno.EIO, 'directory close')
    return result
RecordStore.submit_typed, RecordStore.close, os.close = submit, store_close, close
'''
            self.failure(7, argv=self.args('submit-source-capture'), code='effects_uncertain', prelude=prelude)
            self.assertIsNotNone(self.store.get_submission(self.saved.submission_id))

    def test_input_io_failure_survives_finally_observation_corruption(self):
        """An actual read-path EIO remains operational when later observation detects changed bytes."""
        prelude = f'''
import errno
from pathlib import Path
from research_pipeline import cli_controls
fired = False

def fault(boundary):
    """Change an established input and expose a real I/O failure before reobservation."""
    global fired
    if boundary == 'after_control_read' and not fired:
        fired = True
        with Path({str(self.config)!r}).open('ab') as stream:
            stream.write(b' ')
        raise OSError(errno.EIO, 'read acknowledgement')
cli_controls._fault = fault
'''
        self.failure(6, code='operational_error', prelude=prelude)


class SourceCliRecoveryTests(SourceCliCase):
    """Observe actual canonical outcomes independently of possibly lost CLI acknowledgements."""

    def test_before_commit_rollback_and_after_commit_process_exit(self):
        """The existing transaction seams prove atomic absence versus one recoverable original receipt."""
        before = rows(self.root)
        prelude = '''
import errno
from research_pipeline import store

def fault(boundary):
    """Interrupt a real inserted revision before COMMIT with an I/O-shaped failure."""
    if boundary == 'after_first_revision':
        raise OSError(errno.EIO, 'before commit')
store._fault = fault
'''
        self.failure(7, argv=self.args('submit-source-capture'), code='effects_uncertain', prelude=prelude)
        self.assertEqual(rows(self.root), before)
        prelude = '''
import os
from research_pipeline import store

def fault(boundary):
    """Terminate a real submitting process after COMMIT, without cleanup or acknowledgement."""
    if boundary == 'after_commit':
        os._exit(83)
store._fault = fault
'''
        process = self.invoke(self.args('submit-source-capture'), expected=83, prelude=prelude)
        self.assertEqual((process.stdout, process.stderr), (b'', b''))
        observed = self.result(['inspect-receipt', '--config', str(self.config), '--submission-id', self.saved.submission_id])['receipt']
        before = rows(self.root)
        self.assertEqual(self.result(self.args('submit-source-capture'))['receipt'], observed)
        self.assertEqual(rows(self.root), before)

    def test_actual_sqlite_busy_before_and_after_submission_entry(self):
        """Real independent writer locks retain the pre-entry versus possible-effect distinction."""
        before = rows(self.root)
        for statement, status, code in (('BEGIN IMMEDIATE', 7, 'effects_uncertain'),
                                        ('BEGIN EXCLUSIVE', 6, 'operational_error')):
            with sqlite3.connect(self.root / 'metadata.sqlite3') as lock:
                lock.execute(statement)
                self.failure(status, argv=self.args('submit-source-capture'), code=code)
                lock.rollback()
            self.assertEqual(rows(self.root), before)

    def test_stdout_short_invalid_progress_write_flush_close_and_help(self):
        """Physical prefixes/full bytes never imply acknowledgement when write/flush/close fails."""
        self.result(self.args('submit-source-capture'))
        before = rows(self.root)
        for command in COMMANDS:
            for help_request in (False, True):
                for fault in ('short', 'zero', 'boolean', 'oversized', 'write', 'partial', 'flush', 'close'):
                    prelude = f'''
import os, sys
original = sys.stdout
fault = {fault!r}

class Output:
    """Forward physical stdout with deterministic short/invalid progress and late failures."""
    def __init__(self):
        """Expose the binary interface expected by the existing checked emitter."""
        self.buffer, self.wrote = self, False
    def fileno(self):
        """Retain the original descriptor for safe emitter silencing."""
        return original.fileno()
    def write(self, data):
        """Forward real bytes or return an invalid progress witness."""
        if fault == 'zero':
            return 0
        if fault == 'boolean':
            return True
        if fault == 'oversized':
            return len(data) + 1
        if fault == 'write' or (fault == 'partial' and self.wrote):
            raise BrokenPipeError()
        self.wrote = True
        return os.write(original.fileno(), data[:7] if fault in ('short', 'partial') else data)
    def flush(self):
        """Report flush loss after already delivered complete-looking output."""
        if fault == 'flush':
            raise OSError('flush')
        original.flush()
    def close(self):
        """Report close acknowledgement loss independently of physical byte delivery."""
        if fault == 'close':
            raise OSError('close')
        original.close()
sys.stdout = Output()
'''
                    argv = [command, '--help'] if help_request else self.args(command)
                    status = 0 if fault == 'short' else 7 if command == 'submit-source-capture' and not help_request else 6
                    process = self.invoke(argv, expected=status, prelude=prelude)
                    if status:
                        diagnostic = json.loads(process.stderr)
                        self.assertEqual(diagnostic['code'], 'output_failed')
                        self.assertNotIn('destination', diagnostic['context'])
                        self.assertIn('inspect-receipt' if status == 7 else 'no canonical submission effect',
                                      diagnostic['context']['next_action'])
                        if fault == 'partial':
                            self.assertEqual(len(process.stdout), 7)
                        if fault in ('flush', 'close') and not help_request:
                            self.assertEqual(json.loads(process.stdout)['status'], 'ok')
                    elif not help_request:
                        self.assertEqual(json.loads(process.stdout)['status'], 'ok')
        self.assertEqual(rows(self.root), before)

    def test_physical_closed_stdout_reader_preserves_original_receipt(self):
        """A real broken pipe exits uncertain while inspect-receipt independently recovers the commit."""
        reader, writer = os.pipe()
        os.close(reader)
        try:
            process = subprocess.Popen([sys.executable, '-B', '-m', 'research_pipeline', *self.args('submit-source-capture')],
                cwd=self.parent, env=child_environment(), stdout=writer, stderr=subprocess.PIPE)
        finally:
            os.close(writer)
        _, diagnostic = process.communicate(timeout=45)
        self.assertEqual(process.returncode, 7, diagnostic)
        self.assertEqual(json.loads(diagnostic)['code'], 'output_failed')
        receipt = self.store.get_submission(self.saved.submission_id).to_dict()
        before = rows(self.root)
        self.assertEqual(self.result(self.args('submit-source-capture'))['receipt'], receipt)
        self.assertEqual(rows(self.root), before)

    def test_final_observation_failure_preserves_uncertainty_over_known_refusal(self):
        """A late held-input change cannot certify a refusal's effects after entering submission."""
        from dataclasses import replace
        from research_pipeline.domain import RecordReference, Submission
        from research_pipeline.source import encode_envelope
        from tests.source_cli_fixtures import CREATOR
        value = replace(self.value, supersedes=RecordReference('capture', 2, 'supersedes', 'source'))
        self.write_proposal(Submission('known-cas-refusal', self.saved.provenance,
            [encode_envelope('capture', 3, value, CREATOR)], {'capture': 2}))
        before = rows(self.root)
        prelude = f'''
from pathlib import Path
from research_pipeline.store import RecordStore, RevisionConflictError
real = RecordStore.submit_typed

def submit(self, request):
    """Expose a real deterministic CAS refusal, then invalidate a held observation."""
    try:
        return real(self, request)
    except RevisionConflictError:
        with Path({str(self.proposal)!r}).open('ab') as stream:
            stream.write(b' ')
        raise
RecordStore.submit_typed = submit
'''
        self.failure(7, argv=self.args('submit-source-capture'), code='effects_uncertain', prelude=prelude)
        self.assertEqual(rows(self.root), before)
