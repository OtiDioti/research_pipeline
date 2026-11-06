"""Held-observation mutation, checked-close loss and required metadata/layout corruption."""

from pathlib import Path
import sqlite3

from research_pipeline.store import RecordStore
from tests.resource_fixtures import populate as resources, reservation
from tests.test_claim_use_cli import ClaimUseCliCase, COMMANDS
from tests.test_claim_use_store import metadata


class ClaimUseCliObservationTests(ClaimUseCliCase):
    """Established pins survive failed later acquisitions and never acknowledge substituted controls."""

    def test_leaf_growth_truncation_replacement_deletion_during_reads(self):
        """Mutation at initial stat/open and final EOF/close seams remains integrity failure for both operations."""
        original = self.config.read_bytes()
        before = self.state()
        for command in COMMANDS:
            for boundary in ('before_control_open', 'after_control_read'):
                for mutation in ('growth', 'truncate', 'replace', 'disappear'):
                    prelude = f'''
from pathlib import Path
from research_pipeline import cli_controls
selected = Path({str(self.config)!r})
fired = False

def mutate(point):
    """Mutate the actual observed leaf only once at its selected read seam."""
    global fired
    if fired or point != {boundary!r}:
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
cli_controls._fault = mutate
'''
                    self.failure(command, status=6, code='integrity_error', prelude=prelude)
                    self.config.write_bytes(original)
                    self.config.chmod(0o600)
                    self.assertEqual(self.state(), before)

    def test_detached_earlier_ancestor_when_runtime_acquisition_fails(self):
        """An absent later runtime component cannot conceal replacement of the previously held control parent."""
        controls = self.parent/'controls'
        controls.mkdir(mode=0o700)
        config = controls/'config.json'
        config.write_bytes(self.config.read_bytes())
        config.chmod(0o600)
        detached = self.parent/'detached'
        before = self.state()
        for command in COMMANDS:
            prelude = f'''
from pathlib import Path
from research_pipeline.cli_controls import _ObservedDirectories
real = _ObservedDirectories.open
selected = Path({str(controls)!r})
fired = False

def acquire(self, name, parent=None, *, private=False, exact=False, path=None):
    """Detach the earlier pin then fail the later runtime acquisition without adopting replacements."""
    global fired
    if not fired and str(path) == {str(self.root)!r}:
        fired = True
        selected.rename(Path({str(detached)!r}))
        selected.mkdir(mode=0o700)
        raise FileNotFoundError("later missing component")
    return real(self, name, parent, private=private, exact=exact, path=path)
_ObservedDirectories.open = acquire
'''
            self.failure(command, config=config, status=6, code='integrity_error', prelude=prelude)
            controls.rmdir()
            detached.rename(controls)
            self.assertEqual(self.state(), before)

    def test_late_control_and_directory_reobservation_after_store_close(self):
        """Even successful API reads and successful store close cannot acknowledge late input substitutions."""
        controls = self.parent/'controls'
        controls.mkdir(mode=0o700)
        config = controls/'config.json'
        original = self.config.read_bytes()
        before = self.state()
        for command in COMMANDS:
            for mutation in ('leaf', 'directory'):
                config.write_bytes(original)
                config.chmod(0o600)
                prelude = f'''
from pathlib import Path
from research_pipeline.store import RecordStore
real = RecordStore.close
selected = Path({str(config)!r})

def close(self):
    """Substitute a real control only after the real store handle has closed."""
    real(self)
    if {mutation!r} == "leaf":
        selected.unlink()
    else:
        selected.parent.rename(selected.parent.with_name("detached"))
        selected.parent.mkdir(mode=0o700)
RecordStore.close = close
'''
                self.failure(command, config=config, status=6, code='integrity_error', prelude=prelude)
                if mutation == 'directory':
                    controls.rmdir()
                    (self.parent/'detached').rename(controls)
                self.assertEqual(self.state(), before)

    def test_late_directory_permissions_and_ownership_after_store_close(self):
        """Established config/runtime safety changes disavow real completed reads without canonical writes.

        Real chmod and child-only inode-targeted ownership observations occur only
        after the public API and real close; persisted witnesses prove each seam.
        """
        controls = self.parent/'controls'
        controls.mkdir(mode=0o700)
        config = controls/'config.json'
        config.write_bytes(self.config.read_bytes())
        config.chmod(0o600)
        witness = self.parent/'late-directory-witness'
        before = self.state()
        for command in COMMANDS:
            method = 'claim_use_history' if command == COMMANDS[1] else 'inspect_claim_use'
            for selected in (controls, self.root):
                identity = (selected.stat().st_dev, selected.stat().st_ino)
                for mutation in ('permissions', 'stat-owner', 'fstat-owner'):
                    with self.subTest(command=command, selected=selected, mutation=mutation):
                        prelude = f'''
import os
from pathlib import Path
from research_pipeline import checkout
from research_pipeline.store import RecordStore
real_operation = getattr(RecordStore, {method!r})
real_close = RecordStore.close
real_stat, real_fstat = checkout._stat, os.fstat
selected = Path({str(selected)!r})
witness = Path({str(witness)!r})
completed = False
armed = False

def record(event):
    """Persist actual completed stages independently of the CLI's diagnostic."""
    with witness.open("a") as stream:
        stream.write(event + "\\n")

def operation(self, *args, **kwargs):
    """Finish the genuine selected public operation before allowing any late injection."""
    global completed
    result = real_operation(self, *args, **kwargs)
    completed = True
    record("api")
    return result

def close(self):
    """Close the real store before changing directory mode or arming ownership observations."""
    global armed
    real_close(self)
    assert completed
    record("close")
    if {mutation!r} == "permissions":
        selected.chmod(0o750)
        record("chmod")
    else:
        armed = True

def ownership(result, boundary):
    """Change only UID metadata for the selected held inode at the armed observation boundary."""
    if (armed and boundary + "-owner" == {mutation!r}
            and (result.st_dev, result.st_ino) == {identity!r}):
        fields = list(result)
        fields[4] = os.geteuid()+1
        record(boundary)
        return os.stat_result(fields)
    return result

def stat(parent, name):
    """Observe the real no-follow parent entry before injecting selected ownership metadata."""
    return ownership(real_stat(parent, name), "stat")

def fstat(descriptor):
    """Observe the real held descriptor before injecting selected ownership metadata."""
    return ownership(real_fstat(descriptor), "fstat")

setattr(RecordStore, {method!r}, operation)
RecordStore.close = close
checkout._stat, os.fstat = stat, fstat
'''
                        try:
                            diagnostic = self.failure(command, config=config, status=6,
                                                      code='integrity_error', prelude=prelude)
                            self.assertEqual(diagnostic['context']['config'], str(config))
                            self.assertEqual(diagnostic['context']['use_id'], 'use')
                            events = witness.read_text().splitlines()
                            self.assertEqual(events[:2], ['api', 'close'])
                            self.assertEqual(events[2:], ['chmod' if mutation == 'permissions'
                                                         else mutation.split('-')[0]])
                            self.assertEqual((selected.stat().st_dev, selected.stat().st_ino), identity)
                            if mutation == 'permissions':
                                self.assertEqual(selected.stat().st_mode & 0o7777, 0o750)
                        finally:
                            selected.chmod(0o700)
                            witness.unlink(missing_ok=True)
                        self.assertEqual(self.state(), before)

    def test_checked_input_store_and_held_directory_closes(self):
        """All real resources close before output; any failed close acknowledgement disavows success."""
        resources(self.store)
        self.store.reserve_resources(reservation())
        before = self.state()
        for command in COMMANDS:
            for selected in ('input', 'store', 'directory'):
                prelude = f'''
import errno, os, stat
from research_pipeline import cli_controls
from research_pipeline.store import RecordStore
real_os_close = os.close
real_store_close = RecordStore.close
armed = False

def mark(point):
    """Arm input-close failure after an actual bounded input read."""
    global armed
    if point == "after_control_read" and {selected!r} == "input":
        armed = True

def close_store(self):
    """Close SQLite first, then arm a held directory close or lose store-close acknowledgement."""
    global armed
    real_store_close(self)
    if {selected!r} == "store":
        raise OSError(errno.EIO, "store close")
    if {selected!r} == "directory":
        armed = True

def close_fd(fd):
    """Close a real descriptor once and report a selected EIO without leaking it."""
    global armed
    directory = stat.S_ISDIR(os.fstat(fd).st_mode)
    real_os_close(fd)
    if armed and ({selected!r} == "input" or directory):
        armed = False
        raise OSError(errno.EIO, "checked descriptor close")
cli_controls._fault = mark
RecordStore.close = close_store
os.close = close_fd
'''
                self.failure(command, status=6, code='operational_error', prelude=prelude)
                self.assertEqual(self.state(), before)

    def test_reobservation_io_after_selected_api_disavows_prepared_output(self):
        """A genuine post-read reobservation errno remains operational even after serialization succeeds."""
        before = self.state()
        for command in COMMANDS:
            method = 'claim_use_history' if command == COMMANDS[1] else 'inspect_claim_use'
            prelude = f'''
import errno
from research_pipeline import checkout
from research_pipeline.store import RecordStore
real_operation = getattr(RecordStore, {method!r})
real_stat = checkout._stat
armed = False

def operation(self, *args, **kwargs):
    """Arm only after the selected public operation has produced its genuine complete document."""
    global armed
    result = real_operation(self, *args, **kwargs)
    armed = True
    return result

def stat(parent, name):
    """Fail the later actual config reobservation, retaining the EIO classification."""
    if armed and str(name) == {self.config.name!r}:
        raise OSError(errno.EIO, "late reobservation")
    return real_stat(parent, name)
setattr(RecordStore, {method!r}, operation)
checkout._stat = stat
'''
            self.failure(command, status=6, code='operational_error', prelude=prelude)
            self.assertEqual(self.state(), before)

    def test_failure_path_rechecks_registered_leaf_even_after_read_close_error(self):
        """A read/close exception cannot discard the initial observation before final rechecking."""
        original = self.config.read_bytes()
        for command in COMMANDS:
            prelude = f'''
from pathlib import Path
from research_pipeline import cli_controls
real = cli_controls.read_observed_control

def fail(parent, name, path, maximum, *, modes, before=None):
    """Fail before returning a read observation, then remove the already registered input."""
    Path(path).unlink()
    raise RuntimeError("read did not return")
cli_controls.read_observed_control = fail
'''
            self.failure(command, status=6, code='integrity_error', prelude=prelude)
            self.config.write_bytes(original)
            self.config.chmod(0o600)


class ClaimUseCliIntegrityTests(ClaimUseCliCase):
    """Required metadata and schemas fail truthfully without implicit migration, creation or repair."""

    def test_unsupported_legacy_and_unknown_schema_refusals_are_nonmutating(self):
        """Schemas without claim-use APIs and unknown future schemas remain explicit unsafe-layout refusals."""
        from tests.legacy import create_legacy
        for schema in (1, 2, 3):
            root = self.parent/('legacy-'+str(schema))
            with (create_legacy(root) if schema == 1 else RecordStore.create(root, schema_version=schema)):
                before = metadata(root)
                self.save({**self.config_value, 'store': str(root)})
                for command in COMMANDS:
                    self.failure(command, code='unsafe_layout')
                self.assertEqual(metadata(root), before)
            with sqlite3.connect(root/'metadata.sqlite3') as connection:
                connection.execute('PRAGMA user_version=99')
            before = metadata(root)
            for command in COMMANDS:
                self.failure(command, code='unsafe_layout')
            self.assertEqual(metadata(root), before)
            with sqlite3.connect(root/'metadata.sqlite3') as connection:
                self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 99)

    def test_corrupt_projection_and_required_canonical_metadata_are_integrity_errors(self):
        """Store-opening wrappers retain ClaimUseIntegrityError rather than hiding it as an initial layout error."""
        mutations = ("DELETE FROM claim_use_support_contexts WHERE use_id='use'",
                     "UPDATE revisions SET content_json='{}' WHERE record_id='s-candidate'",
                     "UPDATE claim_use_generations SET causes_json='[]' WHERE use_id='use'")
        for index, sql in enumerate(mutations):
            # Independent genuine stores avoid restoring guessed projection rows.
            root = self.parent/('corrupt-'+str(index))
            from tests.claim_use_fixtures import support_context_graph
            with RecordStore.create(root, schema_version=7) as store:
                support_context_graph(store)
            with sqlite3.connect(root/'metadata.sqlite3') as connection:
                connection.execute(sql)
            self.save({**self.config_value, 'store': str(root)})
            before = metadata(root)
            for command in COMMANDS:
                self.failure(command, status=6, code='integrity_error')
            self.assertEqual(metadata(root), before)

    def test_real_busy_database_remains_operational_without_mutation(self):
        """An independent exclusive SQLite lock tests existing busy handling, not inferred transaction stages."""
        before = self.state()
        for command in COMMANDS:
            with sqlite3.connect(self.root/'metadata.sqlite3') as lock:
                lock.execute('BEGIN EXCLUSIVE')
                try:
                    self.failure(command, status=6, code='operational_error')
                finally:
                    lock.rollback()
            self.assertEqual(self.state(), before)
