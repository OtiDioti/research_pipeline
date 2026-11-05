"""Strict Tool argv, closed authored schemas and independent representation-limit gates."""

from copy import deepcopy
import json
from unittest.mock import patch

from research_pipeline import cli, cli_tools
from research_pipeline.cli_controls import CliError, strict_json
from research_pipeline.domain import DomainValidationError
from research_pipeline.snapshot import SnapshotLimitError
from tests.tool_cli_fixtures import ToolCliCase, canonical
from tests.tool_registration_fixtures import rows

NO_STORE = '''
from research_pipeline.store import RecordStore

def forbidden(*args, **kwargs):
    """Reject any runtime opening before local validation and output reservation have succeeded."""
    raise AssertionError("store opened before local refusal")
RecordStore.open = forbidden
'''
NO_ACCESS = NO_STORE + '''
from research_pipeline import cli_controls, cli_tools

def forbidden_source(*args, **kwargs):
    """Reject source/control discovery on a usage, help or argv-only path."""
    raise AssertionError("resource access before argv validation")
cli_tools.source_root = forbidden_source
cli_controls.read_control = forbidden_source
'''


class ToolCliArgumentTests(ToolCliCase):
    """Guard every resource access on help/usage paths using fresh candidate interpreters."""

    def test_help_and_strict_singletons_before_access(self):
        """Help describes required inputs, limits and effects; malformed syntax never touches resources."""
        for command in ("inspect-tool-record", "submit-tool-records"):
            output = self.invoke([command, "--help"], prelude=NO_ACCESS).stdout.decode()
            self.assertIn("Research execution is unavailable", " ".join(output.split()))
            for name in ("max-content-bytes", "max-envelope-bytes", "max-provenance-depth", "max-total-bytes"):
                self.assertIn("--" + name, output)
            for argv in ([command], self.args(command) + ["--config", str(self.config)],
                         self.args(command) + ["--max-links", "1", "--max-links", "2"],
                         self.args(command) + ["--max-li", "2"], self.args(command) + ["--unknown", "x"],
                         self.args(command) + ["positional"]):
                self.invoke(argv, expected=2, prelude=NO_ACCESS)

    def test_canonical_ascii_argv_numbers_and_ranges(self):
        """Aliases are usage failures; valid syntax with out-of-range values is status 5 before access."""
        for token in ("01", "+1", "-1", " 1", "1 ", "١", "1.0", "1e0", "00", "-0"):
            with self.subTest(token=token):
                self.invoke(self.args("inspect-tool-record", revision=token), expected=2, prelude=NO_ACCESS)
                self.invoke(self.args(max_records=token), expected=2, prelude=NO_ACCESS)
        for options in (dict(revision=0), dict(revision="9" * 500), dict(record_id="bad/id"),
                        dict(kind="evidence"), dict(max_links=65537), dict(config="../unsafe")):
            self.failure(5, argv=self.args("inspect-tool-record", **options), prelude=NO_ACCESS)
        self.failure(5, argv=self.args(max_provenance_depth=25), prelude=NO_ACCESS, code="limit_exceeded")


class ToolBatchCodecTests(ToolCliCase):
    """Exercise complete schema and numeric distinctions locally, independently of filesystem layout."""

    def arguments(self, **options):
        """Parse normal CLI allowances without accessing controls or the runtime."""
        arguments = cli._parser().parse_args(self.args(**options))
        cli._validate(arguments)
        return arguments

    def decode(self, value=None, **options):
        """Apply product local batch decoding to a detached JSON document with explicit caller limits."""
        data = canonical(self.batch_value if value is None else value).encode()
        return cli_tools.decode_batch(data, self.arguments(**options))

    def test_complete_round_trip_preserves_generic_provenance_scalars_and_wire(self):
        """Canonical comparison retains full provenance, including boolean/integer/floating distinctions."""
        actual = self.decode()
        self.assertEqual(canonical(actual.to_dict()), canonical(self.saved.to_dict()))
        details = actual.records[0].provenance.details
        self.assertIs(type(details["integer"]), int)
        self.assertIs(type(details["boolean"]), bool)
        self.assertIs(type(details["float"]), float)
        # The enclosing authored control need not itself have canonical escaping/order.
        alternate = json.dumps(self.batch_value, ensure_ascii=False, indent=2).encode()
        self.assertEqual(cli_tools.decode_batch(alternate, self.arguments()), self.saved)

    def test_every_closed_envelope_submission_and_control_field(self):
        """Missing fields and extensions at each authored boundary cannot acquire runtime state."""
        selectors = (lambda v: v, lambda v: v["submission"],
                     lambda v: v["submission"]["provenance"],
                     lambda v: v["submission"]["records"][0],
                     lambda v: v["submission"]["records"][0]["provenance"],
                     lambda v: v["submission"]["records"][0]["record_references"][0],
                     lambda v: v["submission"]["records"][0]["artifact_references"][0])
        for select in selectors:
            for key in (*select(self.batch_value), "unknown"):
                value = deepcopy(self.batch_value)
                selected = select(value)
                if key == "unknown":
                    selected[key] = None
                else:
                    del selected[key]
                with self.subTest(fields=tuple(selected), key=key), self.assertRaises((DomainValidationError, CliError)):
                    self.decode(value)

    def test_local_invalid_content_identity_projections_heads_and_provenance(self):
        """Public codecs retain nested schema and identity checks; no content falls back to generic submission."""
        mutations = [
            lambda v: v.update(version=True), lambda v: v.update(version=1.0), lambda v: v.update(format="other"),
            lambda v: v["submission"].update(records=[]),
            lambda v: v["submission"].update(expected_heads={}),
            lambda v: v["submission"]["expected_heads"].update(tool=True),
            lambda v: v["submission"]["expected_heads"].update(tool=0.0),
            lambda v: v["submission"]["expected_heads"].update(tool="0"),
            lambda v: v["submission"]["expected_heads"].update(tool=-1),
            lambda v: v["submission"]["expected_heads"].update(tool=9223372036854775808),
            lambda v: v["submission"]["records"].append(deepcopy(v["submission"]["records"][0])),
            lambda v: v["submission"]["provenance"].update(created_at="2026-11-05T09:01:00Z"),
            lambda v: v["submission"]["provenance"].update(details=[]),
        ]
        for field, replacement in (("kind", "evidence"), ("record_id", "wrong"), ("revision", True),
                                   ("revision", 1.0), ("operational_status", "running"), ("content", {}),
                                   ("record_references", []), ("artifact_references", [])):
            def mutate(value, field=field, replacement=replacement):
                """Change one explicit envelope field in a detached control."""
                value["submission"]["records"][0][field] = replacement
            mutations.append(mutate)
        for field, replacement in (("format", "other"), ("version", 2), ("kind", "tool_release"),
                                   ("assessment_id", "other"), ("target", {}), ("attribution", {})):
            def mutate_content(value, field=field, replacement=replacement):
                """Change one required content discriminator/semantic field without regenerating projection."""
                value["submission"]["records"][0]["content"][field] = replacement
            mutations.append(mutate_content)
        for mutate in mutations:
            value = deepcopy(self.batch_value)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises((DomainValidationError, CliError)):
                self.decode(value)

    def test_lexical_duplicate_unicode_numeric_and_nesting_guards(self):
        """Strict batch parsing rejects decoded duplicate keys, UTF-8 defects and integer negative zero."""
        for data in (b'{"a":{"x":1,"\\u0078":2}}', b'{"a":"\xff"}', b'{"a":"\\ud800"}',
                     b'{"a":' + b'9' * 129 + b'}', b'{"a":1e999}', b'{"a":-0}',
                     b'{"a":' + b'[' * 65 + b'0' + b']' * 65 + b'}'):
            with self.subTest(data=data[:30]), self.assertRaises((CliError, DomainValidationError)):
                cli_tools.decode_batch(data, self.arguments())
        # Predecessor strict_json deliberately retains its accepted -0 behavior.
        self.assertEqual(strict_json(b'{"a":-0}'), {"a": 0})

    def test_independent_content_envelope_provenance_metadata_link_and_byte_limits(self):
        """Exact canonical limits succeed; one byte/occurrence less refuses without reconstruction."""
        raw = self.saved.to_dict()
        limits = dict(max_records=len(raw["records"]), max_links=sum(len(r["record_references"]) + len(r["artifact_references"]) for r in raw["records"]),
            max_content_bytes=max(len(canonical(r["content"])) for r in raw["records"]),
            max_envelope_bytes=max(len(canonical(r)) for r in raw["records"]),
            max_provenance_bytes=max(len(canonical(p)) for p in [raw["provenance"], *(r["provenance"] for r in raw["records"])]),
            max_metadata_bytes=len(canonical(raw)), max_file_bytes=self.attachment.size,
            max_total_bytes=self.attachment.size, max_provenance_depth=2)
        self.assertEqual(self.decode(**limits), self.saved)
        for key in limits:
            smaller = {**limits, key: limits[key] - 1}
            with self.subTest(limit=key), self.assertRaises((SnapshotLimitError, DomainValidationError)):
                # max_records=1 is within CLI range and fails at the count guard.
                self.decode(**smaller)
        with patch.object(cli_tools.Submission, "from_dict", side_effect=AssertionError("generic reconstruction reached")):
            with self.assertRaises(SnapshotLimitError):
                self.decode(max_metadata_bytes=len(canonical(raw)) - 1)

    def test_repeated_artifacts_across_envelopes_count_again(self):
        """Repeated direct digests in different envelopes independently consume totals and link occurrences."""
        from research_pipeline.domain import Submission
        from tests.tool_assessment_store_fixtures import assessment
        second = deepcopy(self.doc)
        second["assessment_id"] = "second"
        saved = Submission("repeated", self.saved.provenance,
            [*self.saved.records, assessment(second)], {"assessment": 0, "tool": 0, "second": 0})
        value = {**self.batch_value, "submission": saved.to_dict()}
        self.decode(value, max_total_bytes=2 * self.attachment.size)
        with self.assertRaises(SnapshotLimitError):
            self.decode(value, max_total_bytes=2 * self.attachment.size - 1)


class ToolCliControlRefusalTests(ToolCliCase):
    """Refusal paths prove local invalid controls/output limits cannot enter canonical submission."""

    def test_local_invalid_controls_never_open_store(self):
        """Schema, UTF-8 and duplicate controls fail before protected runtime work."""
        before = rows(self.root)
        for data in (b'{}', b'\xff', b'{"format":1,"format":2}', canonical({**self.batch_value, "version": 2}).encode()):
            self.batch.write_bytes(data)
            self.batch.chmod(0o600)
            self.failure(5, prelude=NO_STORE, code="invalid_input")
            self.assertEqual(rows(self.root), before)

    def test_batch_and_config_byte_limits_and_output_reservation_prevent_effects(self):
        """Input actual bytes, receipt membership/bytes and complete output are independently reserved."""
        before = rows(self.root)
        for options in (dict(max_control_bytes=self.config.stat().st_size - 1),
                        dict(max_batch_bytes=self.batch.stat().st_size - 1), dict(max_records=1),
                        dict(max_receipt_records=1), dict(max_receipt_bytes=1), dict(max_output_bytes=1)):
            self.failure(5, argv=self.args(**options), prelude=NO_STORE, code="limit_exceeded")
            self.assertEqual(rows(self.root), before)

    def test_reservation_boundary_prevents_submission_entry_and_local_invalid_retry(self):
        """One-less output/receipt reservations never enter submit_typed; exact bounds acknowledge unchanged saved input."""
        raw = self.saved.to_dict()
        reservation = dict(submission_id=raw["submission_id"], provenance=raw["provenance"],
            revisions=[[r["record_id"], r["revision"]] for r in raw["records"]],
            fingerprint="0" * 64, event_id=9223372036854775807, committed_at="9999-12-31T23:59:59.999999Z")
        result = dict(format="research_pipeline.cli_result", version=1, command="submit-tool-records", status="ok",
            result=dict(store=str(self.root), batch=str(self.batch), submission_id=self.saved.submission_id, receipt=reservation))
        output_bytes, receipt_bytes = len(canonical(result)) + 1, len(canonical(reservation))
        before = rows(self.root)
        for options in (dict(max_output_bytes=output_bytes - 1), dict(max_receipt_bytes=receipt_bytes - 1)):
            self.failure(5, argv=self.args(**options), prelude=NO_STORE, code="limit_exceeded")
            self.assertEqual(rows(self.root), before)
        self.result(self.args(max_output_bytes=output_bytes, max_receipt_bytes=receipt_bytes,
                              max_control_bytes=self.config.stat().st_size, max_batch_bytes=self.batch.stat().st_size))
        after = rows(self.root)
        self.batch_value["submission"]["records"][0]["content"]["version"] = 2
        self.save(self.batch, self.batch_value)
        self.failure(5, prelude=NO_STORE, code="invalid_input")
        self.assertEqual(rows(self.root), after)
