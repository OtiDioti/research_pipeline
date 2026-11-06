"""Independent exact-fit Source accounts, guarded reconstruction and returned receipt validation."""

import hashlib
import json
from unittest.mock import patch

from research_pipeline import cli, cli_source, source_capture
from research_pipeline.cli_controls import receipt_document
from research_pipeline.domain import CreationProvenance, DomainValidationError, Submission, SubmissionReceipt
from research_pipeline.snapshot import SnapshotLimitError
from tests.source_cli_fixtures import SourceCliCase, canonical
from tests.test_source_cli_controls import COMMANDS, guard
from tests.tool_registration_fixtures import rows


class SourceCliBoundsTests(SourceCliCase):
    """Calculate complete byte accounts with an independent stdlib oracle and actual saved files."""

    def accounts(self, command):
        """Compute all six independent accounts, including worst-case submission receipt and LF."""
        submission = self.saved.to_dict()
        wrapper = json.loads(source_capture.dumps_prepared_submission(self.saved))
        fingerprint_value = dict(fingerprint_version=1, submission=submission)
        fingerprint = hashlib.sha256(canonical(fingerprint_value).encode()).hexdigest()
        common = dict(proposal_path=str(self.proposal), proposal_sha256=hashlib.sha256(self.proposal.read_bytes()).hexdigest(),
                      submission_fingerprint=fingerprint)
        if command == 'inspect-source-proposal':
            document = wrapper
            domain = dict(**common, proposal=wrapper)
        else:
            document = dict(submission_id=self.saved.submission_id, provenance=submission['provenance'],
                revisions=[[r['record_id'], r['revision']] for r in submission['records']], fingerprint='0' * 64,
                event_id=9223372036854775807, committed_at='9999-12-31T23:59:59.999999Z')
            domain = dict(store=str(self.root), **common, receipt=document)
        outer = dict(format='research_pipeline.cli_result', version=1, command=command, status='ok', result=domain)
        s, p, f, d, o = map(lambda value: len(canonical(value)), (submission, wrapper, fingerprint_value, domain, outer))
        return dict(max_control_bytes=len(self.config.read_bytes()), max_proposal_bytes=len(self.proposal.read_bytes()),
            max_metadata_bytes=2*s, max_result_bytes=len(canonical(document)),
            max_serialization_bytes=2*s + 2*p + f + d + o + 1, max_output_bytes=o+1)

    def test_every_account_exact_fit_and_one_unit_deficit_before_protected_work(self):
        """Each allowance independently refuses without store opening, even on a locally over-limit retry."""
        marker = self.parent / 'store-access'
        for command in COMMANDS:
            sizes = self.accounts(command)
            self.result(self.args(command, **sizes))
            before = rows(self.root)
            for option, amount in sizes.items():
                with self.subTest(command=command, account=option):
                    selected = dict(sizes)
                    selected[option] = amount - 1
                    self.failure(5, argv=self.args(command, **selected), code='limit_exceeded', prelude=guard(marker))
                    self.assertFalse(marker.exists())
                    self.assertEqual(rows(self.root), before)

    def test_raw_utf8_whitespace_escape_expansion_and_repeated_metadata(self):
        """Raw file/config bytes, supplementary escapes and repeated full request occurrences are independent."""
        self.config.write_bytes(self.config.read_bytes() + b' ' * 512)
        self.proposal.write_bytes(self.proposal.read_bytes() + b' ' * 1024)
        sizes = self.accounts('inspect-source-proposal')
        self.result(self.args(**sizes))
        for option in ('max_control_bytes', 'max_proposal_bytes'):
            selected = dict(sizes)
            selected[option] -= 1
            self.failure(5, argv=self.args(**selected), code='limit_exceeded')
        s = len(canonical(self.saved.to_dict()))
        self.assertEqual(sizes['max_metadata_bytes'], 2*s)
        self.assertGreater(len(canonical(self.wrapper)), len(json.dumps(self.wrapper, ensure_ascii=False, separators=(',', ':'))))
        self.assertIn('\\ud835\\udc9c', canonical(self.wrapper))
        with patch.object(source_capture, 'loads_prepared_submission', side_effect=AssertionError('reconstructed')):
            for option, amount in (('max_metadata_bytes', 2*s-1), ('max_serialization_bytes', 2*s),
                                   ('max_result_bytes', sizes['max_result_bytes']-1), ('max_output_bytes', sizes['max_output_bytes']-1)):
                arguments = cli._parser().parse_args(self.args(**{option: amount}))
                cli._validate(arguments)
                with self.assertRaises(SnapshotLimitError):
                    cli_source.decode_proposal(self.proposal.read_bytes(), arguments)

    def test_full_provenance_receipt_and_result_reservation_before_store(self):
        """Large nested repeated provenance is retained completely and guarded before runtime acquisition."""
        self.saved = Submission(self.saved.submission_id, CreationProvenance('full-provenance',
            '2026-11-06T10:01:00.000000Z', {'text': '𝒜\n' * 400, 'repeated': ['α' * 300, 'α' * 300]}), self.saved.records, self.saved.expected_heads)
        self.write_proposal()
        sizes = self.accounts('submit-source-capture')
        marker = self.parent / 'store-access'
        for option in ('max_result_bytes', 'max_serialization_bytes', 'max_output_bytes'):
            self.failure(5, argv=self.args('submit-source-capture', **{option: sizes[option]-1}),
                         code='limit_exceeded', prelude=guard(marker))
            self.assertFalse(marker.exists())
        self.assertEqual(self.result(self.args('submit-source-capture', **sizes))['receipt']['provenance'],
                         self.saved.provenance.to_dict())

    def test_returned_receipt_invalid_raw_fields_before_generic_conversion(self):
        """Unexpected receipt scalars, identity, provenance or ordered membership cannot allocate to_dict output."""
        receipt = self.store.submit_typed(self.saved)
        maximum = self.accounts('submit-source-capture')['max_result_bytes']
        self.assertEqual(receipt_document(receipt, self.saved, maximum, maximum), receipt.to_dict())
        for field, value in (('revisions', receipt.revisions * 10000), ('provenance', CreationProvenance('different',
            '2026-11-06T10:01:00.000000Z', {'large': 'x' * 100000})), ('committed_at', 'x' * 100000),
            ('event_id', True), ('event_id', 2**63), ('fingerprint', 'x' * 100000), ('submission_id', 'changed')):
            changed = SubmissionReceipt.from_dict(receipt.to_dict())
            object.__setattr__(changed, field, value)
            with patch.object(SubmissionReceipt, 'to_dict', side_effect=AssertionError('unbounded conversion')):
                with self.assertRaises((DomainValidationError, cli_source.CliError)):
                    receipt_document(changed, self.saved, maximum, maximum)
        for field, value in (('fingerprint', '0' * 64), ('event_id', True), ('provenance', None)):
            prelude = f'''
from research_pipeline.store import RecordStore
real = RecordStore.submit_typed

def submit(self, request):
    """Return a deliberately malformed receipt only after the actual commit acknowledgement."""
    result = real(self, request)
    object.__setattr__(result, {field!r}, {value!r})
    return result
RecordStore.submit_typed = submit
'''
            self.failure(7, argv=self.args('submit-source-capture'), code='effects_uncertain', prelude=prelude)

    def test_diagnostic_worst_case_escaped_paths_and_original_identity(self):
        """Two maximum escaped paths plus exact original IDs fit the unchanged diagnostic byte cap."""
        from research_pipeline.cli_controls import CliError
        context = dict.fromkeys(cli_source.CONTEXT_FIELDS)
        context.update(config='/' + '\x01'*4095, proposal='/' + '\x02'*4095,
            record_id='r'*128, revision=2**63-1, submission_id='s'*128,
            proposal_sha256='a'*64, submission_fingerprint='b'*64,
            next_action=cli_source.guidance('submit-source-capture', None))
        observed = []
        with patch.object(cli.checkout, '_write_all', side_effect=lambda fd, data: observed.append(data)), \
                patch.object(cli.sys, 'stderr') as stream:
            stream.fileno.return_value = 2
            cli._diagnostic('submit-source-capture', CliError(7, 'effects_uncertain', '𝒜'*5000), context)
        self.assertEqual(len(observed), 1)
        self.assertLessEqual(len(observed[0]), 65536)
        self.assertEqual(json.loads(observed[0])['context'], context)
