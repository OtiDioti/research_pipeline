"""Argv, strict configuration, private no-follow controls and early-access witnesses."""

from copy import deepcopy
import errno
import json
import os
from pathlib import Path

from research_pipeline import cli, cli_claim_use
from tests.test_claim_use_cli import ClaimUseCliCase, COMMANDS


def access_guard(marker, *, controls=False):
    """Instrument child-only acquisitions with an independent persisted witness, never an expected error alone."""
    return f'''
from pathlib import Path
from research_pipeline import cli_controls, cli_claim_use
from research_pipeline.store import RecordStore
from research_pipeline.artifacts import ArtifactStore

def forbidden(*args, **kwargs):
    """Persist any forbidden acquisition independently of the resulting CLI classification."""
    Path({str(marker)!r}).write_text("called")
    raise AssertionError("protected acquisition reached")
RecordStore.open = forbidden
ArtifactStore.open = forbidden
if {controls!r}:
    cli_controls.read_control = forbidden
    cli_claim_use.source_root = forbidden
'''


class ClaimUseCliArgumentTests(ClaimUseCliCase):
    """Every syntax/refusal path proves controls and runtime remain untouched."""

    def test_help_and_required_unknown_repeated_abbreviated_positional_options(self):
        """Help documents explicit selection and accounts; usage errors never reach acquisition."""
        marker = self.parent/'access'
        guard = access_guard(marker, controls=True)
        for command in COMMANDS:
            help_text = self.invoke([command, '--help'], prelude=guard).stdout.decode()
            normalized = ' '.join(help_text.split())
            self.assertIn('Research execution is unavailable', normalized)
            self.assertIn('metadata-only', normalized.lower())
            for name, (default, minimum, maximum, unit) in cli_claim_use.specifications(command).items():
                self.assertIn('--'+name.replace('_', '-'), help_text)
                self.assertIn('default '+str(default), normalized)
                self.assertIn(f'range {minimum}..{maximum}', normalized)
            bad = [[command], [command, '--config', str(self.config)], [command, '--use-id', 'use'],
                   self.args(command)+['--config'], self.args(command)+['--use-id'],
                   self.args(command)+['--conf', str(self.config)], self.args(command)+['--unknown', 'x'],
                   self.args(command)+['extra'], self.args(command)+['--config', str(self.config)],
                   self.args(command)+['--use-id', 'other'], self.args(command)+['--revision', '1'],
                   self.args(command)+['--limits', str(self.config)], self.args(command)+['--execute']]
            for name in cli_claim_use.specifications(command):
                flag = '--'+name.replace('_', '-')
                bad.extend((self.args(command)+[flag], self.args(command)+[flag, '1', flag, '2']))
            if command == COMMANDS[0]:
                bad += [self.args(command)+['--after-generation', '0'], self.args(command)+['--page-limit', '1']]
            for argv in bad:
                with self.subTest(argv=argv):
                    self.invoke(argv, expected=2, prelude=guard)
                    self.assertFalse(marker.exists())

    def test_all_numeric_syntax_ranges_and_independent_defaults(self):
        """Canonical aliases fail as usage; huge/overflow values fail as limits before any access."""
        marker = self.parent/'access'
        guard = access_guard(marker, controls=True)
        for command in COMMANDS:
            for name, (default, minimum, maximum, _) in cli_claim_use.specifications(command).items():
                for token in ('01', '+1', '-1', ' 1', '1 ', '١', '１', '1.0', '1e0', '00', '-0'):
                    with self.subTest(command=command, name=name, token=token):
                        self.invoke(self.args(command, **{name: token}), expected=2, prelude=guard)
                        self.assertFalse(marker.exists())
                for token in ('9'*500, maximum+1, *([minimum-1] if minimum else [])):
                    self.failure(command, code='limit_exceeded', prelude=guard, **{name: token})
                    self.assertFalse(marker.exists())
                for endpoint in (minimum, default, maximum):
                    arguments = cli._parser().parse_args(self.args(command, **{name: endpoint}))
                    cli._validate(arguments, dict.fromkeys(cli_claim_use.CONTEXT_FIELDS))
                    self.assertEqual(getattr(arguments, name), endpoint)
        older = cli._parser().parse_args(['submit-tool-records', '--config', str(self.config), '--batch', 'batch'])
        cli._validate(older)
        self.assertEqual((older.max_records, older.max_metadata_bytes), (128, 2097152))

    def test_identifier_paths_and_partial_diagnostic_context(self):
        """Unvalidated selections stay null; normalized established controls remain exact on refusal."""
        marker = self.parent/'access'
        guard = access_guard(marker, controls=True)
        for command in COMMANDS:
            for identity in ('', '_bad', '-bad', 'a/b', 'é', 'a'*129, 'x\n'):
                # Equals keeps a leading dash as the actual ID rather than another option.
                argv = [command, '--config', str(self.config), '--use-id='+identity]
                result = self.invoke(argv, expected=5, prelude=guard)
                diagnostic = json.loads(result.stderr)
                self.assertIsNone(diagnostic['context']['use_id'])
                self.assertEqual(diagnostic['context']['config'], str(self.config))
                self.assertFalse(marker.exists())
            for path in ('../escape', 'x\x00y', '\ud800', 'a'*4097):
                if '\x00' in path or '\ud800' in path:
                    # argv cannot convey NUL/surrogates through exec; exercise the same local validation directly.
                    arguments = cli._parser().parse_args(self.args(command, config=path))
                    with self.assertRaises(ValueError):
                        cli._validate(arguments, dict.fromkeys(cli_claim_use.CONTEXT_FIELDS))
                else:
                    self.failure(command, prelude=guard, config=path,
                                 code='limit_exceeded' if len(path)>4096 else 'unsafe_layout')
                self.assertFalse(marker.exists())
        diagnostic = self.failure(COMMANDS[1], after_generation=9223372036854775808, prelude=guard, code='limit_exceeded')
        self.assertIsNone(diagnostic['context']['after_generation'])
        self.assertIsNone(diagnostic['context']['page_limit'])


class ClaimUseCliConfigurationTests(ClaimUseCliCase):
    """Strict authored controls fail before RecordStore or ArtifactStore acquisition begins."""

    def test_utf8_duplicate_schema_numeric_unicode_depth_and_paths(self):
        """Closed config schemas retain version-one JSON behavior and reject invalid aliases and paths."""
        marker = self.parent/'access'
        guard = access_guard(marker)
        values = []
        for key in self.config_value:
            value = deepcopy(self.config_value)
            del value[key]
            values.append(value)
        values += [{**self.config_value, key: value} for key, value in (
            ('unknown', None), ('format', 'other'), ('version', True), ('version', 1.0), ('version', 2),
            ('store', 'relative'), ('store', '/x/../y'), ('store', '\ud800'), ('store', '/x\x00y'),
            ('protected_roots', None), ('protected_roots', [str(self.root)]*2),
            ('protected_roots', [f'/excluded-{i}' for i in range(65)]))]
        before = self.state()
        for value in values:
            self.config.write_bytes(json.dumps(value).encode('ascii'))
            self.failure(prelude=guard, code=('limit_exceeded' if len(value.get('protected_roots') or [])>64
                else 'unsafe_layout' if value.get('store') == '/x/../y' else 'invalid_input'))
            self.assertFalse(marker.exists())
        for data in (b'\xff', b'{"version":1,"ver\\u0073ion":1}', b'{"a":{"x":1,"\\u0078":2}}',
                     b'{"a":'+b'9'*129+b'}', b'{"a":1e999}', b'{"a":NaN}',
                     b'{"a":'+b'['*65+b'0'+b']'*65+b'}', b'{"a":"\\ud800"}'):
            self.config.write_bytes(data)
            for command in COMMANDS:
                self.failure(command, prelude=guard)
                self.assertFalse(marker.exists())
        self.assertEqual(self.state(), before)

    def test_private_modes_hard_links_symlinks_fifo_nonregular_and_ownership(self):
        """Initially unsafe modes/owners stay layout refusals through repeated checks, before protected access."""
        original = self.config.read_bytes()
        marker = self.parent/'access'
        guard = access_guard(marker)
        before = self.state()
        for command in COMMANDS:
            for mode in (0o644, 0o666, 0o000):
                self.config.chmod(mode)
                self.failure(command, code='unsafe_layout', prelude=guard)
            self.config.chmod(0o600)
            hard = self.parent/'hard'
            os.link(self.config, hard)
            self.failure(command, code='unsafe_layout', prelude=guard)
            hard.unlink()
            self.config.unlink()
            self.config.symlink_to(hard)
            self.failure(command, code='unsafe_layout', prelude=guard)
            self.config.unlink()
            os.mkfifo(self.config, 0o600)
            self.failure(command, code='unsafe_layout', prelude=guard)
            self.config.unlink()
            self.config.mkdir(mode=0o700)
            self.failure(command, code='unsafe_layout', prelude=guard)
            self.config.rmdir()
            self.config.write_bytes(original)
            self.config.chmod(0o600)
            alias = self.parent/'alias'
            alias.symlink_to(self.parent, target_is_directory=True)
            self.failure(command, config=alias/self.config.name, code='unsafe_layout', prelude=guard)
            alias.unlink()
            self.parent.chmod(0o750)
            try:
                self.failure(command, code='unsafe_layout', prelude=guard)
            finally:
                self.parent.chmod(0o700)
            for target in ('leaf', 'parent-stat', 'parent-fstat'):
                selected = self.config if target == 'leaf' else self.parent
                identity = (selected.stat().st_dev, selected.stat().st_ino)
                witness = self.parent/'foreign-owner-witness'
                prelude = guard + f'''
import os
from research_pipeline import checkout
real_stat, real_fstat = checkout._stat, os.fstat

def foreign(result, boundary):
    """Witness initial foreign ownership on one real inode, including repeated cleanup rechecks."""
    if (boundary == {'fstat' if target == 'parent-fstat' else 'stat'!r}
            and (result.st_dev, result.st_ino) == {identity!r}):
        with Path({str(witness)!r}).open("a") as stream:
            stream.write(boundary + "\\n")
        fields = list(result)
        fields[4] = os.geteuid()+1
        return os.stat_result(fields)
    return result

def stat(parent, name):
    """Inject ownership in the selected real no-follow entry observation."""
    return foreign(real_stat(parent, name), "stat")

def fstat(descriptor):
    """Inject ownership in the selected real opened-directory observation."""
    return foreign(real_fstat(descriptor), "fstat")
checkout._stat, os.fstat = stat, fstat
'''
                try:
                    self.failure(command, code='unsafe_layout', prelude=prelude)
                    observations = witness.read_text().splitlines()
                    self.assertEqual(set(observations), {'fstat' if target == 'parent-fstat' else 'stat'})
                    if target != 'leaf':
                        self.assertGreater(len(observations), 2)
                    self.assertFalse(marker.exists())
                finally:
                    witness.unlink(missing_ok=True)
            self.assertFalse(marker.exists())
        self.assertEqual(self.state(), before)

    def test_overlap_both_directions_and_fixed_forbidden_ancestors(self):
        """Lexical bidirectional exclusions and no-content sentinel probes refuse unsafe runtimes and controls."""
        marker = self.parent/'access'
        guard = access_guard(marker)
        source = Path(__file__).resolve().parents[2]
        before = self.state()
        for command in COMMANDS:
            for runtime in (source, source/'nested', source.parent):
                self.save({**self.config_value, 'store': str(runtime)})
                self.failure(command, code='unsafe_layout', prelude=guard)
            for root in (self.root, self.root/'nested', self.parent, self.config, self.config/'nested'):
                self.save({**self.config_value, 'protected_roots': [str(root)]})
                self.failure(command, code='unsafe_layout', prelude=guard)
            for runtime in (self.config, self.config/'nested', self.parent):
                self.save({**self.config_value, 'store': str(runtime)})
                self.failure(command, code='unsafe_layout', prelude=guard)
            self.save(self.config_value)
            for name in ('snapshot.sqlite3', '.backup-incomplete', '.restore-incomplete', '.work-product',
                         'manifest.json', 'intent.json', 'ready.json', 'published.json', 'refresh.json', '.work-product-proposal'):
                sentinel = self.parent/name
                sentinel.write_bytes(b'never read sentinel contents')
                sentinel.chmod(0o000)
                try:
                    self.failure(command, code='unsafe_layout', prelude=guard)
                finally:
                    sentinel.unlink()
            self.assertFalse(marker.exists())
        self.assertEqual(self.state(), before)

    def test_source_control_overlap_and_runtime_forbidden_ancestor_precede_store_open(self):
        """Both lexical source/control directions and held runtime ancestors refuse before protected acquisition."""
        marker = self.parent/'access'
        guard = access_guard(marker)
        before = self.state()
        for command in COMMANDS:
            for source in (self.config, self.config/'executing-source'):
                prelude = guard + f'''
from research_pipeline import cli_claim_use
def source_root():
    """Supply a controlled lexical source location to exercise each overlap direction."""
    return Path({str(source)!r})
cli_claim_use.source_root = source_root
'''
                self.failure(command, code='unsafe_layout', prelude=prelude)
                self.assertFalse(marker.exists())
            controls = self.parent/'source-controls'
            controls.mkdir(mode=0o700)
            config = controls/'config.json'
            config.write_bytes(self.config.read_bytes())
            config.chmod(0o600)
            prelude = guard + f'''
from research_pipeline import cli_claim_use
def source_root():
    """Expose a source parent containing only the selected private control, outside runtime."""
    return Path({str(controls)!r})
cli_claim_use.source_root = source_root
'''
            try:
                self.failure(command, config=config, code='unsafe_layout', prelude=prelude)
                self.assertFalse(marker.exists())
            finally:
                config.unlink()
                controls.rmdir()
            forbidden = self.parent/'forbidden-runtime-parent'
            forbidden.mkdir(mode=0o700)
            sentinel = forbidden/'snapshot.sqlite3'
            sentinel.write_bytes(b'must not be read')
            sentinel.chmod(0o000)
            runtime = forbidden/'runtime'
            runtime.mkdir(mode=0o700)
            self.save({**self.config_value, 'store': str(runtime)})
            try:
                self.failure(command, code='unsafe_layout', prelude=guard)
                self.assertFalse(marker.exists())
            finally:
                runtime.rmdir()
                sentinel.unlink()
                forbidden.rmdir()
                self.save(self.config_value)
            self.assertEqual(self.state(), before)

    def test_real_errno_controls_and_runtime_and_initial_absence(self):
        """True EACCES/EIO remain operational; initial absent runtime never creates a store or domain result."""
        for command in COMMANDS:
            for selected in (self.config.name, self.root.name):
                for number in (errno.EACCES, errno.EIO):
                    prelude = f'''
import os
real = os.stat

def fail(path, *args, **kwargs):
    """Inject a substantive errno at the actual selected no-follow acquisition boundary."""
    if str(path) == {selected!r}:
        raise OSError({number}, "injected IO", path)
    return real(path, *args, **kwargs)
os.stat = fail
'''
                    self.failure(command, status=6, code='operational_error', prelude=prelude)
            self.failure(command, config=self.parent/'missing-config')
            missing = self.parent/'missing-runtime'
            self.save({**self.config_value, 'store': str(missing)})
            self.failure(command, status=3, code='missing')
            self.assertFalse(missing.exists())
            missing.mkdir(mode=0o700)
            try:
                self.failure(command, code='unsafe_layout')
            finally:
                missing.rmdir()
            self.save(self.config_value)
