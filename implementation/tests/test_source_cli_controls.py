"""Source argv, strict saved-file decoding, private controls and exclusion regression tests."""

from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
import os
from pathlib import Path

from research_pipeline import cli, cli_source, source_capture
from research_pipeline.checkout import CheckoutLayoutError
from research_pipeline.snapshot import SnapshotLimitError
from tests.source_cli_fixtures import SourceCliCase
from tests.tool_registration_fixtures import rows

COMMANDS = ('inspect-source-proposal', 'submit-source-capture')


def guard(marker, *, controls=False):
    """Persist a protected-access witness, independently of adapter error classification."""
    return f'''
from pathlib import Path
from research_pipeline import cli_controls, cli_source
from research_pipeline.store import RecordStore

def forbidden(*args, **kwargs):
    """Record a forbidden acquisition before failing the child."""
    Path({str(marker)!r}).write_text('protected operation')
    raise AssertionError('protected operation')
RecordStore.open = forbidden
if {controls!r}:
    cli_controls.read_control = forbidden
'''


class SourceCliControlTests(SourceCliCase):
    """Require invalid invocations and unsafe layouts to fail before protected work."""

    def test_help_required_unknown_repeated_abbreviated_and_positional_argv(self):
        """Only config/proposal and six finite accounts are accepted; help performs no acquisition."""
        marker = self.parent / 'access'
        for command in COMMANDS:
            help_text = self.invoke([command, '--help'], prelude=guard(marker, controls=True)).stdout.decode()
            for name, (default, minimum, maximum, _) in cli_source.SPECIFICATIONS.items():
                self.assertIn('--' + name.replace('_', '-'), help_text)
                normalized = ' '.join(help_text.split())
                self.assertIn('default ' + str(default), normalized)
                self.assertIn(f'range {minimum}..{maximum}', normalized)
            bad = [[command], [command, '--config', str(self.config)], [command, '--proposal', str(self.proposal)]]
            bad += [self.args(command) + extra for extra in (
                ['--config', str(self.config)], ['--proposal', str(self.proposal)], ['--conf', 'x'],
                ['--unknown', 'x'], ['positional'], ['--limits', 'x'], ['--kind', 'source'],
                ['--record-id', 'capture'], ['--revision', '2'], ['--submission-id', 'new'], ['--stdin'])]
            for name in cli_source.SPECIFICATIONS:
                flag = '--' + name.replace('_', '-')
                bad.extend((self.args(command) + [flag], self.args(command) + [flag, '1', flag, '2']))
            for argv in bad:
                with self.subTest(argv=argv):
                    self.invoke(argv, expected=2, prelude=guard(marker, controls=True))
            self.assertFalse(marker.exists())

    def test_all_numeric_spellings_ranges_and_older_defaults(self):
        """Canonical syntax is checked before bounded conversion; older contracts keep their defaults."""
        for command in COMMANDS:
            for name, (default, minimum, maximum, _) in cli_source.SPECIFICATIONS.items():
                for token in ('00', '01', '+1', '-1', '-0', ' 1', '1 ', '١', '１', '1.0', '1e0'):
                    with self.subTest(command=command, name=name, token=token), redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as error:
                            cli._parser().parse_args(self.args(command, **{name: token}))
                        self.assertEqual(error.exception.code, 2)
                for token in ('9' * 500, maximum + 1, minimum - 1):
                    arguments = cli._parser().parse_args(self.args(command, **{name: token}))
                    with self.assertRaises(SnapshotLimitError):
                        cli._validate(arguments)
                for endpoint in (minimum, default, maximum):
                    arguments = cli._parser().parse_args(self.args(command, **{name: endpoint}))
                    cli._validate(arguments)
                    self.assertEqual(getattr(arguments, name), endpoint)
        old = cli._parser().parse_args(['inspect-record', '--config', 'config', '--record-id', 'id', '--revision', '01'])
        cli._validate(old)
        self.assertEqual((old.revision, old.max_output_bytes, old.max_metadata_bytes), (1, 2097152, 2097152))
        for path in ('', 'x\x00y', '\ud800', '../escape', 'a' * 4097):
            arguments = cli._parser().parse_args(self.args(config=path))
            with self.assertRaises((ValueError, SnapshotLimitError, CheckoutLayoutError)):
                cli._validate(arguments)

    def test_strict_json_numeric_depth_unicode_and_source_codec_semantics(self):
        """Guards reject malformed authored JSON before reconstruction and retain Source negative-zero semantics."""
        marker = self.parent / 'store-access'
        data = self.proposal.read_bytes()
        malformed = [b'\xff', b'{"format":1,"format":2}', b'{', b'"\\ud800"',
            b'[' * 65 + b'0' + b']' * 65, b'{"x":' + b'1' * 129 + b'}',
            b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}']
        for raw in malformed:
            self.proposal.write_bytes(raw)
            for command in COMMANDS:
                diagnostic = self.failure(5, argv=self.args(command), code='invalid_input', prelude=guard(marker))
                self.assertIsNone(diagnostic['context']['submission_id'])
            self.assertFalse(marker.exists())
        # Source's numeric semantics permit -0 as an ordinary JSON integer in
        # descriptive provenance; the Tool-only integer restriction is excluded.
        wrapper = deepcopy(self.wrapper)
        wrapper['submission']['provenance']['details']['zero'] = 0
        raw = json.dumps(wrapper).replace('"zero": 0', '"zero": -0').encode()
        self.proposal.write_bytes(raw)
        self.assertEqual(self.result()['proposal'], json.loads(source_capture.dumps_prepared_submission(
            source_capture.loads_prepared_submission(raw))))
        self.proposal.write_bytes(data)

    def test_incomplete_forged_cross_format_generic_and_mixed_requests(self):
        """The authoritative Source codec rejects omitted nested fields and wrong wrapper/member types."""
        marker = self.parent / 'store-access'
        mutations = [
            lambda v: v.update(format='research_pipeline.work_product_submission'),
            lambda v: v.update(format='research_pipeline.cli_tool_batch'),
            lambda v: v.update(version=2), lambda v: v.update(version=True),
            lambda v: v['submission']['records'].append(deepcopy(v['submission']['records'][0])),
            lambda v: v['submission']['records'][0].update(kind='claim'),
            lambda v: v['submission']['expected_heads'].update(capture=0),
            lambda v: v['submission']['records'][0]['content'].pop('limitations'),
            lambda v: v['submission']['records'][0]['content']['reading'].pop('limitations'),
            lambda v: v['submission']['records'][0]['content']['originals'][0]['provenance'].pop('notes'),
            lambda v: v['submission']['records'][0].update(record_references=[]),
            lambda v: v['submission']['records'][0].update(artifact_references=[]),
            lambda v: v['submission'].update(submission_id='not/valid'),
            lambda v: v['submission']['records'][0].update(revision=True),
            lambda v: v['submission']['records'][0]['content']['originals'][0]['artifact'].update(size=1.0),
        ]
        for mutate in mutations:
            value = deepcopy(self.wrapper)
            mutate(value)
            self.save(self.proposal, value)
            for command in COMMANDS:
                self.failure(5, argv=self.args(command), code='invalid_input', prelude=guard(marker))
            self.assertFalse(marker.exists())

    def test_initial_missing_config_proposal_runtime_and_private_file_shapes(self):
        """Only initially missing proposal/runtime are missing; private regular leaf/parent rules are enforced."""
        before = rows(self.root)
        self.failure(5, argv=self.args(config=self.parent / 'missing'), code='invalid_input')
        self.failure(3, argv=self.args(proposal=self.parent / 'missing'), code='missing')
        missing = self.parent / 'missing-runtime'
        self.save(self.config, {**self.config_value, 'store': str(missing)})
        self.assertEqual(self.result()['proposal'], self.wrapper)
        self.failure(3, argv=self.args('submit-source-capture'), code='missing')
        self.assertFalse(missing.exists())
        self.save(self.config, self.config_value)
        for path in (self.config, self.proposal):
            data = path.read_bytes()
            for mode in (0o000, 0o644, 0o666, 0o700):
                path.chmod(mode)
                self.failure(5, code='unsafe_layout')
            path.chmod(0o600)
            hard = self.parent / 'hard-link'
            os.link(path, hard)
            self.failure(5, code='unsafe_layout')
            hard.unlink()
            path.unlink()
            for shape in ('symlink', 'fifo', 'directory'):
                if shape == 'symlink':
                    path.symlink_to('nonexistent')
                elif shape == 'fifo':
                    os.mkfifo(path, 0o600)
                else:
                    path.mkdir(mode=0o700)
                self.failure(5, code='unsafe_layout')
                path.rmdir() if shape == 'directory' else path.unlink()
            path.write_bytes(data)
            path.chmod(0o400)
            self.result()
            path.chmod(0o600)
        alias = self.parent / 'alias'
        alias.symlink_to(self.parent, target_is_directory=True)
        self.failure(5, argv=self.args(config=alias / self.config.name), code='unsafe_layout')
        self.parent.chmod(0o750)
        try:
            self.failure(5, code='unsafe_layout')
        finally:
            self.parent.chmod(0o700)
        self.assertEqual(rows(self.root), before)

    def test_source_runtime_protected_control_overlap_and_fixed_sentinels(self):
        """Bidirectional lexical exclusion precedes detectable acquisition without directory enumeration."""
        source = Path(__file__).resolve().parents[2]
        marker = self.parent / 'store-access'
        for selected in (source, source / 'missing', source.parent):
            for option in ('config', 'proposal'):
                self.failure(5, argv=self.args(**{option: selected}), code='unsafe_layout', prelude=guard(marker, controls=True))
            self.save(self.config, {**self.config_value, 'store': str(selected)})
            self.failure(5, code='unsafe_layout', prelude=guard(marker))
        self.save(self.config, self.config_value)
        self.failure(5, argv=self.args(proposal=self.config), code='unsafe_layout')
        for root in (self.root, self.parent, self.proposal, self.proposal / 'child'):
            self.save(self.config, {**self.config_value, 'protected_roots': [str(root)]})
            self.failure(5, code='unsafe_layout', prelude=guard(marker))
        self.save(self.config, self.config_value)
        for sentinel in ('snapshot.sqlite3', '.backup-incomplete', '.work-product', 'manifest.json', 'refresh.json', '.work-product-proposal'):
            path = self.parent / sentinel
            path.write_bytes(b'must never be read')
            path.chmod(0o000)
            try:
                self.failure(5, code='unsafe_layout', prelude=guard(marker))
            finally:
                path.unlink()
        self.assertFalse(marker.exists())

    def test_config_closed_fields_strict_values_paths_and_scalar_guards(self):
        """Invalid config remains authored input and never opens the selected runtime or proposal."""
        marker = self.parent / 'store-access'
        variants = [None, {}, {**self.config_value, 'extra': 0},
            {**self.config_value, 'version': True}, {**self.config_value, 'version': 1.0},
            {**self.config_value, 'format': 'other'}, {**self.config_value, 'store': 'relative'},
            {**self.config_value, 'protected_roots': None},
            {**self.config_value, 'protected_roots': [str(self.parent)] * 2},
            {**self.config_value, 'store': '\ud800'},
            {**self.config_value, 'protected_roots': [str(self.parent / str(i)) for i in range(65)]}]
        for value in variants:
            self.config.write_text(json.dumps(value, ensure_ascii=True))
            for command in COMMANDS:
                self.failure(5, argv=self.args(command),
                    code='limit_exceeded' if isinstance(value, dict) and isinstance(value.get('protected_roots'), list)
                        and len(value['protected_roots']) > 64 else 'invalid_input', prelude=guard(marker))
            self.assertFalse(marker.exists())
        for data in (b'\xff', b'{"version":1,"version":1}', b'['*65 + b'0' + b']'*65,
                     b'{"x":NaN}', b'{"x":' + b'1'*129 + b'}'):
            self.config.write_bytes(data)
            self.failure(5, code='invalid_input', prelude=guard(marker))
        self.assertFalse(marker.exists())

    def test_initial_foreign_ownership_leaf_and_parent_remains_unsafe(self):
        """Initially foreign stat/fstat ownership is unsafe layout, not an established late mutation."""
        for selected in (self.parent, self.config, self.proposal):
            for probe in ('stat', 'fstat'):
                prelude = f'''
import os
selected = os.stat({str(selected)!r})
real = os.{probe}

def probe(*args, **kwargs):
    """Keep physical identity while reporting an initially untrusted owner at the OS seam."""
    value = real(*args, **kwargs)
    if (value.st_dev, value.st_ino) == (selected.st_dev, selected.st_ino):
        fields = list(value)
        fields[4] = value.st_uid + 1
        return os.stat_result(fields)
    return value
os.{probe} = probe
'''
                self.failure(5, code='unsafe_layout', prelude=prelude)
