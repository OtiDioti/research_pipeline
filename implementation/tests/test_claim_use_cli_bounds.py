"""Independent real-graph work, metadata, representation and stdout acknowledgement bounds."""

from dataclasses import replace
import errno
import json
import os
import subprocess
import sys
from unittest.mock import patch

from research_pipeline import cli, cli_claim_use
from research_pipeline.claim_use import ClaimUseLimitError, ClaimUseIntegrityError
from research_pipeline.cli_controls import CliError
from research_pipeline.store import StoreLayoutError, ReferenceResolutionError, StoreBusyError
from tests.claim_use_fixtures import LIMITS, PROVENANCE, batch, review, assessment_envelope
from tests.resource_fixtures import populate as resources, reservation
from tests.test_claim_use_context import context_record
from tests.test_claim_use_cli import ClaimUseCliCase, COMMANDS, canonical
from tests.test_vault import child_environment


class ClaimUseCliBudgetTests(ClaimUseCliCase):
    """Observe genuine API account boundaries without replacing results or lowering hard limits."""

    def test_actual_control_domain_and_complete_output_exact_byte_boundaries(self):
        """UTF-8, escaped domain JSON, repeated identities, outer framing and LF are separate accounts."""
        self.store.submit(batch('unicode', [context_record('support-evidence', question='α 😀 " \\ \n')]))
        resources(self.store)
        self.store.reserve_resources(reservation())
        before = self.state()
        control_bytes = len(self.config.read_bytes())
        self.assertNotEqual(control_bytes, len(self.config.read_text()))
        for command in COMMANDS:
            document = self.equivalent(command)
            domain_bytes = len(canonical(document))-1
            process = self.invoke(self.args(command))
            output_bytes = len(process.stdout)
            self.assertGreater(output_bytes, domain_bytes+1)
            if command == COMMANDS[0]:
                self.assertGreater(domain_bytes, len(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()))
            exact = dict(max_control_bytes=control_bytes, max_result_bytes=domain_bytes, max_output_bytes=output_bytes)
            self.assertEqual(self.invoke(self.args(command, **exact)).stdout, process.stdout)
            for name in exact:
                options = {**exact, name: exact[name]-1}
                self.failure(command, code='limit_exceeded', **options)
                # Unrelated maximum accounts cannot pay another exhausted account.
                options = {name: exact[name]-1, **{key: cli_claim_use.LIMITS[key][2]
                           for key in ('max_control_bytes', 'max_result_bytes', 'max_output_bytes', 'max_metadata_bytes') if key != name}}
                self.failure(command, code='limit_exceeded', **options)
                self.assertEqual(self.state(), before)

    def test_graph_count_assertion_history_and_metadata_sufficient_boundaries(self):
        """Real downstream graphs and assertion histories enforce independent inclusive caller accounts."""
        value = review('s-candidate', 's-route-a', 'support-target')
        for revision in range(2, 5):
            self.store.submit_typed(batch('assertion-'+str(revision), [assessment_envelope('s-review-a', revision,
                replace(value, reviewer='attributed '+str(revision)), PROVENANCE)]))
        expected = self.store.inspect_claim_use('downstream-use', limits=LIMITS).to_dict()
        before = self.state()
        for name in ('max_bindings', 'max_records', 'max_references', 'max_assertion_revisions', 'max_metadata_bytes'):
            rejected, admitted = 0, getattr(LIMITS, name)
            while admitted-rejected > 1:
                amount = (admitted+rejected)//2
                try:
                    self.store.inspect_claim_use('downstream-use', limits=replace(LIMITS, **{name: amount}))
                except ClaimUseLimitError:
                    rejected = amount
                else:
                    admitted = amount
            self.assertGreater(admitted, 1, name)
            # Limits are selected only through the public constructor and argv;
            # this search never patches a reader, global ceiling or result.
            self.assertEqual(self.store.inspect_claim_use('downstream-use', limits=replace(LIMITS, **{name: admitted})).to_dict(), expected)
            self.equivalent(use_id='downstream-use', **{name: admitted})
            self.failure(use_id='downstream-use', code='limit_exceeded', **{name: admitted-1, 'max_output_bytes': 16777216})
            self.assertEqual(self.state(), before)

    def test_history_forwarding_no_artificial_graph_work_and_metadata_boundary(self):
        """History forwards all six unchanged while leaving unconsumed graph accounts at one."""
        selected = dict(max_bindings=1, max_records=1, max_references=1, max_assertion_revisions=1,
                        max_metadata_bytes=67108864, max_result_bytes=4194304)
        prelude = f'''
from pathlib import Path
from research_pipeline.store import RecordStore
real = RecordStore.claim_use_history

def history(self, identity, *, after_generation, limit, limits):
    """Observe exact forwarding independently while still executing the genuine history operation."""
    import json
    Path("forwarded").write_text(json.dumps(dict(use_id=identity, after_generation=after_generation,
        limit=limit, limits={{name: getattr(limits, name) for name in {tuple(selected)!r}}})))
    return real(self, identity, after_generation=after_generation, limit=limit, limits=limits)
RecordStore.claim_use_history = history
'''
        self.equivalent(COMMANDS[1], after_generation=0, page_limit=1, prelude=prelude, **selected)
        forwarded = json.loads((self.parent/'forwarded').read_bytes())
        self.assertEqual(forwarded, dict(use_id='use', after_generation=0, limit=1, limits=selected))
        expected = self.store.claim_use_history('use', limits=LIMITS).to_dict()
        rejected, admitted = 0, LIMITS.max_metadata_bytes
        while admitted-rejected > 1:
            amount = (admitted+rejected)//2
            try:
                self.store.claim_use_history('use', limits=replace(LIMITS, max_metadata_bytes=amount))
            except ClaimUseLimitError:
                rejected = amount
            else:
                admitted = amount
        self.equivalent(COMMANDS[1], **{**selected, 'max_metadata_bytes': admitted})
        self.failure(COMMANDS[1], code='limit_exceeded', max_metadata_bytes=admitted-1,
                     max_output_bytes=16777216)
        self.assertGreater(admitted, len(canonical(expected)))

    def test_classification_wrapped_integrity_real_errno_and_diagnostic_size(self):
        """Types/chained errno determine failures; escaped text preserves all exact context selections."""
        cases = ((ClaimUseLimitError('bounded'), 'limit_exceeded', 5),
                 (ClaimUseIntegrityError('corrupt'), 'integrity_error', 6),
                 (StoreLayoutError('unsupported'), 'unsafe_layout', 5),
                 (ReferenceResolutionError('missing reference'), 'integrity_error', 6),
                 (StoreBusyError('busy'), 'operational_error', 6))
        for error, code, status in cases:
            failure = cli_claim_use.classify(error, {})
            self.assertEqual((failure.code, failure.status), (code, status))
        for cause in (ClaimUseIntegrityError('broken'), OSError(errno.EACCES, 'denied'), OSError(errno.EIO, 'io')):
            error = StoreLayoutError('wrapper')
            error.__cause__ = cause
            self.assertEqual(cli_claim_use.classify(error, {}).code,
                             'integrity_error' if isinstance(cause, ClaimUseIntegrityError) else 'operational_error')
        from tempfile import TemporaryFile
        context = dict(config='/'+'α'*2047, use_id='u'*128, after_generation=9223372036854775807,
                       page_limit=256, next_action='Repeat using context selections; discard partial output.')
        with TemporaryFile(dir='/tmp') as stream:
            with patch.object(cli.sys, 'stderr', stream):
                cli._diagnostic(COMMANDS[1], CliError(6, 'operational_error', '😀'*1000), context)
            stream.seek(0)
            data = stream.read()
        self.assertLessEqual(len(data), 65536)
        self.assertEqual(json.loads(data)['context'], context)
        self.assertTrue(data.isascii())


class ClaimUseCliOutputTests(ClaimUseCliCase):
    """Physical delivery never overrides failed read-only acknowledgement or mutates canonical state."""

    def test_drained_short_writes_zero_invalid_write_prefix_flush_and_close_loss(self):
        """Inspect physical bytes and status independently, including complete-looking unacknowledged documents."""
        resources(self.store)
        self.store.reserve_resources(reservation())
        before = self.state()
        for command in COMMANDS:
            expected = self.invoke(self.args(command)).stdout
            for fault in ('short', 'zero', 'none', 'negative', 'over', 'bool', 'write', 'prefix', 'flush', 'close'):
                prelude = f'''
import os, sys
original = sys.stdout
fault = {fault!r}

class Output:
    """Deliver real stdout bytes with deterministic byte-progress and acknowledgement faults."""
    def __init__(self):
        """Expose the existing emitter's binary interface and per-process write state."""
        self.buffer = self
        self.wrote = False
    def fileno(self):
        """Retain the actual recipient descriptor for failure silencing."""
        return original.fileno()
    def write(self, data):
        """Drain real short writes or expose invalid progress and physical prefix loss."""
        if fault == "write" or (fault == "prefix" and self.wrote):
            raise BrokenPipeError()
        if fault in ("zero", "none", "negative", "over", "bool"):
            return {{"zero": 0, "none": None, "negative": -1, "over": len(data)+1, "bool": True}}[fault]
        self.wrote = True
        return os.write(original.fileno(), data[:7] if fault in ("short", "prefix") else data)
    def flush(self):
        """Lose acknowledgement after physical delivery without implying canonical effects."""
        if fault == "flush":
            raise OSError("flush loss")
        original.flush()
    def close(self):
        """Report close failure even when the delivered bytes look complete."""
        if fault == "close":
            raise OSError("close loss")
        original.close()
sys.stdout = Output()
'''
                result = self.invoke(self.args(command), expected=0 if fault == 'short' else 6, prelude=prelude)
                if fault == 'short':
                    self.assertEqual(result.stdout, expected)
                else:
                    diagnostic = json.loads(result.stderr)
                    self.assertEqual(diagnostic['code'], 'output_failed')
                    self.assertIn('discard partial output', diagnostic['context']['next_action'])
                    self.assertNotIn('inspect-receipt', diagnostic['context']['next_action'])
                    self.assertEqual(result.stdout, expected if fault in ('flush', 'close') else expected[:7] if fault == 'prefix' else b'')
                self.assertEqual(self.state(), before)
            reader, writer = os.pipe()
            os.close(reader)
            try:
                process = subprocess.Popen([sys.executable, '-B', '-m', 'research_pipeline', *self.args(command)],
                    cwd=self.parent, env=child_environment(), stdout=writer, stderr=subprocess.PIPE)
            finally:
                os.close(writer)
            _, diagnostic = process.communicate(timeout=45)
            self.assertEqual(process.returncode, 6, diagnostic)
            self.assertEqual(json.loads(diagnostic)['code'], 'output_failed')
            self.assertEqual(self.state(), before)

    def test_help_output_failure_uses_only_claim_use_context(self):
        """A failed new-command help acknowledgement uses the same bounded context without selections."""
        prelude = '''
import sys
from research_pipeline import cli

def fail(data):
    """Refuse help output without closing the test process's diagnostic channel."""
    raise OSError("help output lost")
cli._emit = fail
'''
        for command in COMMANDS:
            process = self.invoke([command, '--help'], expected=6, prelude=prelude)
            self.assertEqual(process.stdout, b'')
            diagnostic = json.loads(process.stderr)
            self.assertEqual(diagnostic['command'], command)
            self.assertEqual(diagnostic['code'], 'output_failed')
            self.assertEqual(set(diagnostic['context']), set(cli_claim_use.CONTEXT_FIELDS))
            self.assertEqual({k: v for k, v in diagnostic['context'].items() if k != 'next_action'},
                             dict.fromkeys(('config', 'use_id', 'after_generation', 'page_limit')))
