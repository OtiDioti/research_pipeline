"""Selected Tool read preflight, snapshot isolation and sufficient receipt/output reservations."""

from copy import deepcopy
import json
import sqlite3
import threading
from unittest.mock import patch

from research_pipeline import cli, cli_tools
from research_pipeline.snapshot import SnapshotIntegrityError, SnapshotLimitError
from research_pipeline.tool_release import ToolRelease
from tests.tool_cli_fixtures import ToolCliCase, canonical
from tests.tool_registration_fixtures import rows


class ToolCliSelectedBoundsTests(ToolCliCase):
    """Use real selected metadata and direct bytes without invoking fresh admission or source traversal."""

    def arguments(self, command="inspect-tool-record", **options):
        """Build validated caller limits without control/runtime access."""
        result = cli._parser().parse_args(self.args(command, **options))
        cli._validate(result)
        return result

    def setUp(self):
        """Commit one mixed request before testing exact selected read reservations."""
        super().setUp()
        self.receipt = self.store.submit_typed(self.saved)

    def test_selected_independent_guards_precede_parsing_store_body_and_verification(self):
        """Every small allowance stops before raw parsing, reconstruction or direct object verification."""
        budgets = dict(max_content_bytes=1, max_envelope_bytes=1, max_provenance_bytes=1,
                       max_metadata_bytes=1, max_links=0, max_file_bytes=self.attachment.size - 1,
                       max_total_bytes=self.attachment.size - 1)
        for option, amount in budgets.items():
            with self.subTest(option=option), patch.object(cli_tools, "_stored_json", side_effect=AssertionError("parsed")), \
                    patch.object(self.store, "_get_typed_revision", side_effect=AssertionError("reconstructed")), \
                    patch.object(self.store._artifacts, "verify", side_effect=AssertionError("verified")):
                with self.assertRaises(SnapshotLimitError):
                    cli_tools.inspect_selected(self.store, self.arguments(**{option: amount}))

    def test_selected_content_and_direct_bytes_exact_fit(self):
        """Content equality and per-direct/total-byte equality succeed while one-less remains effective."""
        arguments = self.arguments(max_content_bytes=len(canonical(self.doc)),
                                   max_file_bytes=self.attachment.size, max_total_bytes=self.attachment.size)
        envelope, doc, commit = cli_tools.inspect_selected(self.store, arguments)
        self.assertEqual(envelope.to_dict(), self.assessed.to_dict())
        self.assertEqual(doc, self.doc)
        self.assertEqual(commit, {key: self.receipt.to_dict()[key] for key in ("submission_id", "committed_at", "fingerprint")})
        with self.assertRaises(SnapshotLimitError):
            cli_tools.inspect_selected(self.store, self.arguments(max_content_bytes=len(canonical(self.doc)) - 1))

    def test_provenance_depth_lexical_gate_precedes_typed_body(self):
        """The caller's depth-one allowance rejects nested creator details before store reconstruction."""
        with patch.object(self.store, "_get_typed_revision", side_effect=AssertionError("reconstructed")):
            with self.assertRaises(SnapshotLimitError):
                cli_tools.inspect_selected(self.store, self.arguments(max_provenance_depth=1))
        cli_tools.inspect_selected(self.store, self.arguments(max_provenance_depth=2))

    def test_selected_storage_types_ordinals_and_canonical_json_are_integrity_errors(self):
        """Corrupt links, joins, scalar storage and malformed canonical JSON never reach artifact reads."""
        cases = [
            ("UPDATE record_links SET ordinal=2 WHERE record_id='assessment'", (),
             "UPDATE record_links SET ordinal=0 WHERE record_id='assessment'", ()),
            ("UPDATE artifact_links SET digest=x'00' WHERE record_id='assessment'", (),
             "UPDATE artifact_links SET digest=? WHERE record_id='assessment'", (self.attachment.digest,)),
            ("UPDATE revisions SET content_json=? WHERE record_id='assessment'", (json.dumps(self.doc),),
             "UPDATE revisions SET content_json=? WHERE record_id='assessment'", (canonical(self.doc),)),
            ("UPDATE revisions SET provenance_json=? WHERE record_id='assessment'", ('{"actor":"x","actor":"y"}',),
             "UPDATE revisions SET provenance_json=? WHERE record_id='assessment'", (canonical(self.assessed.provenance.to_dict()),)),
        ]
        for change, params, restore, restored_params in cases:
            with self.subTest(sql=change):
                self.damage(change, params)
                with patch.object(self.store._artifacts, "verify", side_effect=AssertionError("verified corrupt metadata")):
                    with self.assertRaises(SnapshotIntegrityError):
                        cli_tools.inspect_selected(self.store, self.arguments())
                self.damage(restore, restored_params)

    def test_wrong_kind_precedes_other_kind_artifact_verification(self):
        """A mismatched explicit kind refuses without verifying the selected assessment's direct bytes."""
        with patch.object(self.store._artifacts, "verify", side_effect=AssertionError("wrong kind artifacts")):
            with self.assertRaises(cli_tools.CliError) as caught:
                cli_tools.inspect_selected(self.store, self.arguments(kind="tool_release"))
        self.assertEqual(caught.exception.status, 5)

    def test_guard_typed_read_and_commit_share_one_sqlite_snapshot(self):
        """A real competing writer cannot change content between preflight and the shared store body."""
        pending = threading.Event()
        failures = []
        amended = deepcopy(self.doc)
        amended["limitations"] = {"state": "known", "value": ["later supplied report"], "reason": None}
        def writer():
            """Hold an actual write transaction until the selected reader releases its snapshot."""
            try:
                with sqlite3.connect(self.root / "metadata.sqlite3", timeout=10) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("UPDATE revisions SET content_json=? WHERE record_id='assessment'", (canonical(amended),))
                    pending.set()
                    connection.commit()
            except BaseException as error:
                failures.append(error)
                pending.set()
        original = self.store._get_typed_revision
        thread = threading.Thread(target=writer)
        def read(connection, record_id, revision):
            """Start the actual writer after guard reads and retain the same connection for typed decoding."""
            thread.start()
            if not pending.wait(5):
                raise AssertionError("writer did not prepare")
            return original(connection, record_id, revision)
        with patch.object(self.store, "_get_typed_revision", side_effect=read):
            result = cli_tools.inspect_selected(self.store, self.arguments())
        thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(result[1], self.doc)
        self.assertEqual(result[2]["submission_id"], self.saved.submission_id)
        self.assertEqual(cli_tools.inspect_selected(self.store, self.arguments())[1], amended)

    def test_envelope_and_metadata_conservative_reservation_exact_boundaries(self):
        """Independently count scalar upper bounds, SQL fetch contributions and fixed JSON framing."""
        raw = self.assessed.to_dict()
        receipt = self.receipt.to_dict()
        commit = {name: receipt[name] for name in ("submission_id", "committed_at", "fingerprint")}
        def bound(text):
            """Mirror only the documented six-ASCII-bytes-per-UTF8-byte upper bound."""
            return max(4, 6 * len(text.encode()) + 2)
        def object_size(values):
            """Count fixed JSON punctuation plus independently supplied value fragment sizes."""
            return 2 + max(0, len(values) - 1) + sum(len(canonical(key)) + 1 + amount for key, amount in values.items())
        def array_size(items):
            """Count array separators and supplied independent element sizes."""
            return 2 + max(0, len(items) - 1) + sum(items)
        refs = [object_size({"record_id": bound(r["record_id"]), "revision": len(str(r["revision"])),
            "relationship": bound(r["relationship"]), "target_kind": bound(r["target_kind"])}) for r in raw["record_references"]]
        artifacts = [object_size({"digest": bound(r["digest"]), "size": len(str(r["size"]))}) for r in raw["artifact_references"]]
        e = object_size(dict(record_id=bound(raw["record_id"]), revision=1, kind=bound(raw["kind"]),
            content=len(canonical(raw["content"])), provenance=len(canonical(raw["provenance"])),
            operational_status=4, scientific_disposition=4, record_references=array_size(refs), artifact_references=array_size(artifacts)))
        # The selected request occurs at ordinal zero; its commit has event ID one.
        fields = [raw["kind"], canonical(raw["content"]), canonical(raw["provenance"]), "", "",
                  receipt["submission_id"], receipt["committed_at"], receipt["fingerprint"], "0", raw["record_id"], "1",
                  raw["record_id"], receipt["submission_id"], receipt["submission_id"], "submission_committed", "1"]
        f = sum(len(value.encode()) for value in fields)
        for group in (raw["record_references"], raw["artifact_references"]):
            for ordinal, row in enumerate(group):
                f += sum(len(str(value).encode()) for value in row.values()) + len(str(ordinal)) + len(raw["record_id"]) + 1
        k = object_size({name: bound(value) for name, value in commit.items()})
        m = 2 * f + 2 * e + k
        cli_tools.inspect_selected(self.store, self.arguments(max_envelope_bytes=e, max_metadata_bytes=m))
        for options in (dict(max_envelope_bytes=e - 1), dict(max_metadata_bytes=m - 1)):
            with self.assertRaises(SnapshotLimitError):
                cli_tools.inspect_selected(self.store, self.arguments(**options))


class ToolCliReservationTests(ToolCliCase):
    """Check sufficient result allowance independently before any runtime lookup or mutation."""

    def test_receipt_and_complete_output_exact_fit_and_one_less(self):
        """A saved-request-only worst-case receipt bounds the full result, paths, ASCII expansion and LF."""
        reservation = dict(submission_id=self.saved.submission_id, fingerprint="0" * 64,
            event_id=9223372036854775807, committed_at="9999-12-31T23:59:59.999999Z",
            provenance=self.saved.provenance.to_dict(), revisions=[[r.record_id, r.revision] for r in self.saved.records])
        result = dict(format="research_pipeline.cli_result", version=1, command="submit-tool-records", status="ok",
            result=dict(store=str(self.root), batch=str(self.batch), submission_id=self.saved.submission_id, receipt=reservation))
        receipt_bytes, output_bytes = len(canonical(reservation)), len(canonical(result)) + 1
        def arguments(**options):
            """Decode explicit reservation limits without touching any control or runtime."""
            value = cli._parser().parse_args(self.args(**options))
            cli._validate(value)
            return value
        self.assertEqual(cli_tools._receipt_reservation(arguments(max_receipt_bytes=receipt_bytes,
                         max_output_bytes=output_bytes), self.saved, self.root), receipt_bytes)
        for opts in (dict(max_receipt_bytes=receipt_bytes - 1), dict(max_output_bytes=output_bytes - 1)):
            with self.assertRaises(SnapshotLimitError):
                cli_tools._receipt_reservation(arguments(**opts), self.saved, self.root)
        self.assertEqual(len(self.store.audit_events()), 0)

    def test_returned_receipt_raw_bounds_precede_conversion(self):
        """Unexpected returned membership/provenance is uncertain before generic receipt copying."""
        from research_pipeline.cli_controls import receipt_document
        from research_pipeline.domain import CreationProvenance, SubmissionReceipt, DomainValidationError
        receipt = self.store.submit_typed(self.saved)
        arguments = cli._parser().parse_args(self.args())
        cli._validate(arguments)
        size = cli_tools._receipt_reservation(arguments, self.saved, self.root)
        self.assertEqual(receipt_document(receipt, self.saved, arguments.max_receipt_bytes, size), receipt.to_dict())
        for field, value in (("revisions", receipt.revisions * 10000),
                             ("provenance", CreationProvenance("different", "2026-11-05T10:00:00.000000Z", {"x": "a" * 200000})),
                             ("committed_at", "x" * 10000)):
            changed = SubmissionReceipt.from_dict(receipt.to_dict())
            object.__setattr__(changed, field, value)
            with patch.object(SubmissionReceipt, "to_dict", side_effect=AssertionError("unbounded conversion")):
                with self.assertRaises(DomainValidationError):
                    receipt_document(changed, self.saved, arguments.max_receipt_bytes, size)



class ToolCliClassificationTests(ToolCliCase):
    """Exercise diagnostic precedence without claiming transaction-stage certainty from exception text."""

    def test_known_refusals_and_unknown_post_entry_effects(self):
        """Typed refusals keep their classifications; unknown operational failures after entry remain uncertain."""
        from research_pipeline.artifacts import ArtifactIOError, ArtifactNotFoundError
        from research_pipeline.domain import DomainValidationError
        from research_pipeline.store import ReferenceResolutionError, RevisionConflictError, StoreBusyError
        cases = [(DomainValidationError("local"), 5, "invalid_input"),
                 (SnapshotLimitError("bounded"), 5, "limit_exceeded"),
                 (RevisionConflictError("changed"), 4, "conflict"),
                 (ReferenceResolutionError("closure"), 6, "integrity_error"),
                 (ArtifactNotFoundError("direct"), 6, "integrity_error")]
        for error, status, code in cases:
            self.assertEqual((cli_tools.classify(error, {"submit_entered": True}).status,
                              cli_tools.classify(error, {"submit_entered": True}).code), (status, code))
        for error in (StoreBusyError("busy"), ArtifactIOError("I/O"), OSError("unknown"), KeyboardInterrupt()):
            self.assertEqual(cli_tools.classify(error, {}).status, 6)
            self.assertEqual(cli_tools.classify(error, {"submit_entered": True}).status, 7)
        self.assertEqual(cli_tools.classify(DomainValidationError("late conversion"), {"returned": True}).status, 7)
        output = cli_tools.CliError(7, "output_failed", "lost stdout")
        self.assertIs(cli_tools.classify(output, {"returned": True}), output)

    def test_bounded_diagnostic_retains_two_worst_case_paths_and_original_identity(self):
        """ASCII explanatory text shrinks while complete established paths/ID survive the diagnostic cap."""
        import tempfile
        context = dict(config="/" + "α" * 2047, batch="/" + "β" * 2047, kind=None,
                       record_id=None, revision=None, submission_id="original-id", next_action="Inspect original saved context.")
        failure = cli_tools.CliError(7, "effects_uncertain", "😀" * 1000)
        with tempfile.TemporaryFile() as stream:
            with patch.object(cli.sys, "stderr", stream):
                cli._diagnostic("submit-tool-records", failure, context)
            stream.seek(0)
            raw = stream.read()
        self.assertLessEqual(len(raw), 65536)
        self.assertTrue(raw.isascii())
        self.assertEqual(json.loads(raw)["context"], context)
