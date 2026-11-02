"""Actual dossier failures, source restrictions, historical integrity and bounded preflight."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import operating_authority as a
from research_pipeline.domain import RecordEnvelope
from research_pipeline.store import RecordStore
from research_pipeline.source import SourceDeclaration, encode_envelope as source_envelope
from research_pipeline.project import encode_envelope as project_envelope
from research_pipeline.work_product import encode_envelope as product_envelope
from tests.operating_fixtures import TIME, LIMITS, policy, scope, short_note, decision, prepare, sign, empty
from tests.test_store import CREATOR, request, record
from tests.test_project import readiness
from tests.test_corpus import missing
from tests.test_typed_store import ref


class OperatingReadinessTests(unittest.TestCase):
    """Use real source/document objects and controlled malformed SQLite metadata without weakening validators."""

    def setUp(self):
        """Create a disposable private runtime outside source and register ordered cleanup."""
        temporary = TemporaryDirectory(prefix="authority-readiness-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)

    def inspect(self, limits=LIMITS):
        """Inspect current main-research authority using only explicit time, host policy and budgets."""
        return self.store.inspect_operating_eligibility("synthetic", "project", purpose="main_research",
            policy=policy(), evaluated_at=TIME, limits=limits).to_dict()

    def approve(self):
        """Commit actual short-note bytes and a fully bound authenticated synthetic main approval."""
        setup, source, records = short_note(self.store)
        permission = scope("main_research", data=True)
        signed = sign(decision(prepare(self.store, permission), permission))
        result = self.store.commit_operating_decision(signed, policy=policy(), evaluated_at=TIME, limits=LIMITS)
        return setup, source, records, signed, result

    def assert_retention_boundary(self, make_call, constructor, prerequisite, *, receipt=False):
        """Reach a real public constructor at S-1 and S remaining bytes after real prerequisite work.

        Each factory supplies a public call and a post-call durable-state check.
        The test-only charge isolates this stage from earlier natural peaks, using
        the real reserve method. Only that artificial charge is released after a
        successful constructor so later stages can finish with their normal budget.
        """
        from research_pipeline import operating_authority_store as module
        reserve = module._Reader.reserve
        construct = getattr(*constructor)
        resolve = getattr(*prerequisite)
        reservations, boundaries, completed = [], [], []

        def resolved(*args, **kwargs):
            """Mark prerequisite completion only after its real implementation returns."""
            value = resolve(*args, **kwargs)
            completed.append(True)
            return value

        def observe(reader, size):
            """Record actual allowance attempts while preserving the production budget check."""
            reservations.append((reader.metadata_bytes, size))
            return reserve(reader, size)

        def constructed(*args, **kwargs):
            """Record the constructor's reservation boundary and validate the real value."""
            self.assertTrue(completed)
            boundaries.append(len(reservations) - 1)
            value = construct(*args, **kwargs)
            charged = reservations[-1][1]
            if receipt:
                self.assertGreater(charged, len(a.canonical(value.to_dict())))
            else:
                self.assertEqual(charged, len(a.canonical(value.to_dict())))
            return value

        call, verify = make_call()
        with patch.object(module._Reader, "reserve", observe), \
                patch.object(*prerequisite, autospec=True, side_effect=resolved), \
                patch.object(*constructor, side_effect=constructed):
            baseline = call(LIMITS)
        verify(baseline)
        self.assertEqual(len(boundaries), 1)
        target = boundaries[0]
        expected_before, expected_size = reservations[target]
        if receipt:
            actual_receipt = baseline.to_dict()["receipt"]
            actual_size = len(a.canonical(actual_receipt)) + len(a.canonical(baseline.to_dict()))
            self.assertEqual(expected_size - actual_size, 2 * (19 - len(str(actual_receipt["event_id"]))))
        for extra_byte in (1, 0):
            completed.clear()
            attempts, observed, charged_readers = [], [], []
            call, verify = make_call()

            def charge(reader, size):
                """Exhaust exactly the intended stage, never masking an earlier failure."""
                index = len(observed)
                incoming = reader.metadata_bytes, size
                observed.append(incoming)
                if index <= target:
                    self.assertEqual(incoming, reservations[index])
                if index == target:
                    self.assertTrue(completed)
                    attempts.append(incoming)
                    additional = reader.limits.max_metadata_bytes - reader.metadata_bytes - size + extra_byte
                    self.assertGreaterEqual(additional, 0)
                    reserve(reader, additional)
                    self.assertEqual(reader.limits.max_metadata_bytes - reader.metadata_bytes, size - extra_byte)
                    charged_readers.append((reader, additional))
                return reserve(reader, size)

            def construct_at_equality(*args, **kwargs):
                """Require reservation success before real construction; release only the test charge."""
                self.assertFalse(extra_byte, "constructor reached with S-1 bytes")
                self.assertEqual(attempts, [(expected_before, expected_size)])
                reader, additional = charged_readers[0]
                self.assertEqual(reader.metadata_bytes, reader.limits.max_metadata_bytes)
                value = construct(*args, **kwargs)
                reader.metadata_bytes -= additional
                return value

            result = None
            with self.subTest(extra_byte=extra_byte, constructor=constructor[1]), \
                    patch.object(module._Reader, "reserve", charge), \
                    patch.object(*prerequisite, autospec=True, side_effect=resolved), \
                    patch.object(*constructor, side_effect=construct_at_equality) as target_constructor:
                if extra_byte:
                    with self.assertRaises(a.AuthorityLimitError):
                        call(LIMITS)
                else:
                    result = call(LIMITS)
                self.assertEqual(attempts, [(expected_before, expected_size)])
                self.assertTrue(completed)
                self.assertEqual(target_constructor.call_count, 0 if extra_byte else 1)
            verify(result)
        return baseline

    def assert_output_boundary(self, call, expected):
        """Exercise independent public output equality and one-byte overflow with ample metadata."""
        size = len(a.canonical(expected.to_dict()))
        with self.assertRaisesRegex(a.AuthorityLimitError, "detached result byte limit"):
            call(replace(LIMITS, max_result_bytes=size - 1))
        self.assertEqual(call(replace(LIMITS, max_result_bytes=size)), expected)

    def test_binding_retention_before_preparation_and_fresh_approval(self):
        """Both public resolver callers reserve complete bindings, including escaped artifact selectors."""
        from research_pipeline import operating_authority_store as module
        short_note(self.store, document_path="résumé.md")
        permission = scope("main_research", data=True)

        def call(limits):
            """Prepare the real complete short-note binding with the supplied independent bounds."""
            return self.store.prepare_operating_binding(ref("project", "project_setup", "project"),
                scope=permission, limits=limits)

        def verify(result):
            """Require populated evidence and canonical escaping on every successful preparation."""
            if result is not None:
                wire = result.to_dict()
                self.assertTrue(wire["record_evidence"])
                self.assertTrue(wire["head_expectations"])
                self.assertIn("résumé.md", [item["selector"] for item in wire["artifact_evidence"]])
                self.assertIn(r"r\u00e9sum\u00e9.md", a.canonical(wire))

        result = self.assert_retention_boundary(lambda: (call, verify), (module, "OperatingBinding"),
            (RecordStore, "_check_typed_targets"))
        self.assert_output_boundary(call, result)
        self.assert_retention_boundary(lambda: self.fresh_append_call("approve"),
            (module, "OperatingBinding"), (RecordStore, "_check_typed_targets"))

    def test_history_retention_empty_and_populated(self):
        """Empty and annotated populated histories own a separate complete detached snapshot."""
        from research_pipeline import operating_authority_store as module

        def call(limits):
            """Inspect the actual complete stream without consulting artifacts or a clock."""
            return self.store.inspect_operating_history("synthetic", "project", policy=policy(), limits=limits)

        for populated in (False, True):
            if populated:
                short_note(self.store, document_path="résumé.md")
                permission = scope("main_research", data=True)
                signed = sign(decision(prepare(self.store, permission), permission,
                    rationale='A "quoted" café observation\nremains procedural.'))
                self.store.commit_operating_decision(signed, policy=policy(), evaluated_at=TIME, limits=LIMITS)
            else:
                with patch.object(module, "AuthorityHistory", side_effect=AssertionError("unreserved empty history")) as constructor:
                    with self.assertRaises(a.AuthorityLimitError):
                        call(replace(LIMITS, max_metadata_bytes=1))
                    constructor.assert_not_called()

            def verify(result):
                """Assert actual decisions and annotations survive the independent snapshot copy."""
                if result is not None:
                    entries = result.to_dict()["decisions"]
                    self.assertEqual(len(entries), int(populated))
                    if entries:
                        self.assertEqual(entries[0]["signature_status"], "verified")
                        self.assertEqual(entries[0]["policy_status"], "permitted")
                        self.assertEqual(entries[0]["envelope"]["content"]["decision"]["rationale"],
                            'A "quoted" café observation\nremains procedural.')

            with self.subTest(populated=populated):
                result = self.assert_retention_boundary(lambda: (call, verify),
                    (module, "AuthorityHistory"), (module, "_history"))
                self.assert_output_boundary(call, result)

    def test_binding_retention_includes_absent_optional_pins(self):
        """An incomplete setup still reserves its full unavailable-pin objects and empty collections."""
        from research_pipeline import operating_authority_store as module
        empty(self.store)

        def call(limits):
            """Prepare actual incomplete metadata without granting research readiness."""
            return self.store.prepare_operating_binding(ref("project", "project_setup", "project"),
                scope=None, limits=limits)

        def verify(result):
            """Keep explicit absent pins and empty artifact evidence visible in the detached binding."""
            if result is not None:
                wire = result.to_dict()
                for name in ("context", "brief", "intake_report"):
                    self.assertEqual(wire["dossier"][name], a.absent())
                self.assertEqual(wire["artifact_evidence"], [])

        result = self.assert_retention_boundary(lambda: (call, verify),
            (module, "OperatingBinding"), (RecordStore, "_check_typed_targets"))
        self.assert_output_boundary(call, result)

    def test_eligibility_retention_empty_noneligible_and_complete(self):
        """All result fields consume retention even without decisions or usable current trust."""
        from research_pipeline import operating_authority_store as module
        current_policy = policy()

        def call(limits):
            """Inspect one actual snapshot with explicit trust, time, purpose and independent limits."""
            return self.store.inspect_operating_eligibility("synthetic", "project", purpose="main_research",
                policy=current_policy, evaluated_at=TIME, limits=limits)

        with patch.object(module, "EligibilityResult", side_effect=AssertionError("unreserved empty eligibility")) as constructor:
            with self.assertRaises(a.AuthorityLimitError):
                call(replace(LIMITS, max_metadata_bytes=1))
            constructor.assert_not_called()
        for status in ("no_decision", "missing_trust", "eligible_main_research"):
            if status == "missing_trust":
                short_note(self.store, document_path="résumé.md")
                permission = scope("main_research", data=True)
                signed = sign(decision(prepare(self.store, permission), permission))
                self.store.commit_operating_decision(signed, policy=policy(), evaluated_at=TIME, limits=LIMITS)
                current_policy = None
            elif status == "eligible_main_research":
                current_policy = policy()

            def verify(result):
                """Check selected status and complete evidence rather than just constructor calls."""
                if result is not None:
                    wire = result.to_dict()
                    self.assertEqual(wire["status"], status)
                    self.assertTrue(wire["recheck_required"])
                    if status != "no_decision":
                        self.assertTrue(wire["binding"]["artifact_evidence"])
                        self.assertEqual(len(wire["history_signatures"]), 1)
                    if status == "eligible_main_research":
                        self.assertTrue(wire["eligible"])
                        self.assertTrue(wire["observed_heads"])
                        self.assertEqual(len(wire["verified_artifacts"]), 3)
                        self.assertIsNotNone(wire["policy_fingerprint"])

            with self.subTest(status=status):
                prerequisite = "_fresh" if status == "eligible_main_research" else "_history"
                result = self.assert_retention_boundary(lambda: (call, verify),
                    (module, "EligibilityResult"), (module, prerequisite))
                self.assert_output_boundary(call, result)

    def fresh_append_call(self, outcome):
        """Build a fresh equivalent real fixture and verify append atomicity and original-ID recovery."""
        from research_pipeline import operating_authority_store as module
        index = len(list(self.parent.glob("append-*")))
        store = RecordStore.create(self.parent / ("append-" + str(index)))
        self.addCleanup(store.close)
        short_note(store, document_path="résumé.md")
        permission = scope("main_research", data=True)
        binding = prepare(store, permission)
        signed = sign(decision(binding, permission))
        operation = "approve" if outcome == "approve" else outcome + "-next"
        if outcome != "approve":
            store.commit_operating_decision(signed, policy=policy(), evaluated_at=TIME, limits=LIMITS)
            signed = sign(decision(binding, revision=2, previous=a.encode_envelope(signed),
                outcome=outcome, operation=operation))
        before = tuple(store._connection.iterdump())
        identity = signed.to_dict()["decision"]["decision_id"]
        previous_head = store.head(identity)

        def call(limits):
            """Observe insertion and fresh result construction, preserving all production checks."""
            insert = store._insert_submission
            make_receipt = store._receipt
            make_result = module._result
            fresh_results = []

            def result(envelope, receipt):
                """Distinguish fresh construction from predecessor recovery in a reduction's history."""
                if receipt.submission_id == operation:
                    fresh_results.append(True)
                return make_result(envelope, receipt)

            with patch.object(store, "_insert_submission", wraps=insert) as insertion, \
                    patch.object(store, "_receipt", wraps=make_receipt) as receipt_path, \
                    patch.object(module, "_result", side_effect=result):
                try:
                    value = store.commit_operating_decision(signed, policy=policy(), evaluated_at=TIME, limits=limits)
                except a.AuthorityLimitError as error:
                    if "aggregate metadata" in str(error):
                        insertion.assert_not_called()
                        receipt_path.assert_not_called()
                        self.assertFalse(fresh_results)
                    else:
                        self.assertIn("detached result byte limit", str(error))
                        insertion.assert_called_once()
                        receipt_path.assert_called_once()
                        self.assertEqual(fresh_results, [True])
                    self.assertEqual(tuple(store._connection.iterdump()), before)
                    self.assertEqual(store.head(identity), previous_head)
                    self.assertIsNone(store._connection.execute(
                        "SELECT 1 FROM submissions WHERE submission_id=?", (operation,)).fetchone())
                    raise
                insertion.assert_called_once()
                receipt_path.assert_called_once()
                self.assertEqual(fresh_results, [True])
                return value

        def verify(result):
            """Compare a fresh commit with later metadata-only recovery and check exact head advancement."""
            if result is None:
                self.assertEqual(tuple(store._connection.iterdump()), before)
                self.assertIsNone(store.get_operating_operation(operation, limits=LIMITS))
            else:
                self.assertEqual(store.head(identity), 1 if previous_head is None else previous_head + 1)
                self.assertEqual(store.get_operating_operation(operation, limits=LIMITS), result)
                self.assertEqual(store.commit_operating_decision(signed, policy=None, evaluated_at=None, limits=LIMITS), result)

        return call, verify

    def test_fresh_append_retention_precedes_insert_and_receipt(self):
        """Approval and successor reduction reserve receipt plus complete result before the shared insert."""
        from research_pipeline import store as store_module
        for outcome in ("approve", "revoke"):
            with self.subTest(outcome=outcome):
                self.assert_retention_boundary(lambda: self.fresh_append_call(outcome),
                    (store_module, "SubmissionReceipt"), (RecordStore, "_check_batch"), receipt=True)
                # Use another actually fresh operation for each cap. Its timestamp
                # has fixed width and event ID is identical across equivalent fixtures.
                call, verify = self.fresh_append_call(outcome)
                baseline = call(LIMITS)
                verify(baseline)
                size = len(a.canonical(baseline.to_dict()))
                call, verify = self.fresh_append_call(outcome)
                with self.assertRaisesRegex(a.AuthorityLimitError, "detached result byte limit"):
                    call(replace(LIMITS, max_result_bytes=size - 1))
                verify(None)
                result = call(replace(LIMITS, max_result_bytes=size))
                verify(result)
                self.assertEqual(len(a.canonical(result.to_dict())), size)

    def test_missing_corrupt_and_unsafe_selected_objects(self):
        """Loss/corruption/unsafe modes of actual source, brief and intake objects explicitly remove eligibility."""
        _, source, records, signed, original = self.approve()
        selected = [source.originals[0].artifact, records[-2].artifact_references[0], records[-1].artifact_references[0]]
        for artifact in selected:
            path = self.root / "objects" / artifact.digest
            raw, mode = path.read_bytes(), path.stat().st_mode & 0o777
            for damage in ("missing", "corrupt", "writable"):
                with self.subTest(digest=artifact.digest, damage=damage):
                    if damage == "missing":
                        path.unlink()
                    elif damage == "corrupt":
                        path.chmod(0o600)
                        path.write_bytes(b"X" * len(raw))
                        path.chmod(mode)
                    else:
                        path.chmod(0o600)
                    self.assertEqual(self.inspect()["status"], "artifact_unavailable")
                    self.assertEqual(self.store.get_operating_operation("approve", limits=LIMITS), original)
                    self.assertEqual(self.store.commit_operating_decision(signed, policy=None, evaluated_at=None, limits=LIMITS), original)
                    if path.exists():
                        path.chmod(0o600)
                        path.unlink()
                    self.assertEqual(self.store.put_artifact(raw), artifact)
            self.assertTrue(self.inspect()["eligible"])
        for limits in (replace(LIMITS, max_artifacts=0), replace(LIMITS, max_file_bytes=1), replace(LIMITS, max_total_bytes=0)):
            with self.assertRaises(a.AuthorityLimitError):
                self.inspect(limits)

    def test_restrictions_original_selection_and_cross_project_sources(self):
        """Every explicit data permission independently enforces access/reuse/external/public and original membership."""
        _, source, _ = short_note(self.store)
        for original in ("text", "license", "absent"):
            wire = scope("setup", data=True).to_dict()
            wire["data_access"][0]["original_ids"] = [original]
            with self.subTest(original=original), self.assertRaises(a.AuthorityReadinessError):
                prepare(self.store, a.OperatingScope(wire))
        wire = scope("setup", data=True).to_dict()
        wire["data_access"][0]["source"]["record_id"] = "elsewhere"
        with self.assertRaises(a.AuthorityReadinessError):
            prepare(self.store, a.OperatingScope(wire))
        self.store.submit(request("policy-evidence", [record("disclosure-policy", kind="event")]))
        base = scope("setup", data=True).to_dict()
        base["data_access"][0]["operations"] = ["read", "reuse", "external_processing"]
        base["disclosures"] = [{"source": ref("capture", "disclosed_source", "source").to_dict(),
            "original_ids": ["original"], "recipient_id": "recipient", "policy_reference": ref("disclosure-policy", "disclosure_policy", "event").to_dict()}]
        prepare(self.store, a.OperatingScope(base))
        connection = self.store._connection
        original = connection.execute("SELECT content_json FROM revisions WHERE record_id='capture'").fetchone()[0]
        for field, statuses in (("access", ("unknown", "unavailable", "limited")),
                                ("reuse", ("unknown", "restricted", "prohibited")),
                                ("external_processing", ("unknown", "restricted", "prohibited")),
                                ("confidentiality", ("unknown", "restricted", "confidential"))):
            for status in statuses:
                # These are actual stored typed declarations, not monkeypatched predicates.
                restrictions = replace(source.restrictions, **{field: SourceDeclaration(status, "Synthetic restriction")})
                changed = source_envelope("capture", 1, replace(source, restrictions=restrictions), CREATOR)
                connection.execute("UPDATE revisions SET content_json=? WHERE record_id='capture'", (a.canonical(changed.content),))
                with self.subTest(field=field, status=status), self.assertRaises(a.AuthorityReadinessError):
                    prepare(self.store, a.OperatingScope(base))
                connection.execute("UPDATE revisions SET content_json=? WHERE record_id='capture'", (original,))
        undisclosed = deepcopy(base); undisclosed["disclosures"] = []
        with self.assertRaises(a.AuthorityReadinessError):
            prepare(self.store, a.OperatingScope(undisclosed))

    def test_empty_reference_only_partial_and_unauthenticated_proposals(self):
        """Empty/reference-only dossiers and actually missing optional documents cannot acquire main readiness."""
        for index, entries in enumerate(([], [missing("reference", "reference_only")])):
            with RecordStore.create(self.parent / ("empty" + str(index))) as store:
                empty(store, entries=entries)
                permission = scope("main_research")
                signed = sign(decision(prepare(store, permission), permission))
                with self.assertRaises(a.AuthorityReadinessError):
                    store.commit_operating_decision(signed, policy=policy(), evaluated_at=TIME, limits=LIMITS)
        setup, _, _ = short_note(self.store)
        permission = scope("main_research", data=True)
        binding = prepare(self.store, permission)
        # Even a syntactically affirmed imported proposal requires actual configured authentication.
        signed = sign(decision(binding, permission))
        with self.assertRaises(a.AuthorityAuthenticationError):
            self.store.commit_operating_decision(signed, policy=None, evaluated_at=TIME, limits=LIMITS)
        partial = replace(setup, brief=None, readiness=readiness("incomplete_intake"),
            supersedes=ref("project", "supersedes", "project"))
        self.store.submit_typed(request("partial", [project_envelope("project", 2, partial, CREATOR)], {"project": 1}))
        binding = self.store.prepare_operating_binding(ref("project", "project_setup", "project", 2), scope=permission, limits=LIMITS)
        with self.assertRaises(a.AuthorityReadinessError):
            self.store.commit_operating_decision(sign(decision(binding, permission)), policy=policy(), evaluated_at=TIME, limits=LIMITS)

    def test_hidden_work_product_and_source_history_cannot_reset(self):
        """Generic-admitted missing predecessors on selected typed inputs cannot conceal earlier history."""
        setup, source, records = short_note(self.store)
        for identity, record_value in (("capture", source_envelope("capture", 2, source, CREATOR)),
                                       ("brief", RecordEnvelope.from_dict({**records[-2].to_dict(), "revision": 2}))):
            self.store.submit(request("generic-" + identity, [record_value], {identity: 1}))
        # A standalone bound head can be inspected through a selected dossier history
        # only after the exact corpus/project pins are coherent; never auto-follow heads.
        from research_pipeline.operating_authority_store import _Reader
        from research_pipeline.store import _decode_typed_envelope
        with self.store._transaction() as connection:
            reader = _Reader(self.store, connection, LIMITS)
            for identity in ("capture", "brief"):
                actual = reader.read((identity, 2))
                with self.assertRaises(a.AuthorityIntegrityError):
                    reader.history(actual, _decode_typed_envelope(actual))

    def test_original_metadata_corruption_and_size_preflight(self):
        """Real stored duplicate keys, fingerprints, membership, oversized links and missing history fail closed."""
        _, _, _, signed, _ = self.approve()
        connection = self.store._connection
        identity = signed.to_dict()["decision"]["decision_id"]
        original = connection.execute("SELECT request_json,fingerprint FROM submissions WHERE submission_id='approve'").fetchone()
        for text, fingerprint in ((original[0].replace('"fingerprint_version":1', '"fingerprint_version":1,"fingerprint_version":1'), original[1]),
                                  (original[0], "0" * 64)):
            connection.execute("UPDATE submissions SET request_json=?,fingerprint=? WHERE submission_id='approve'", (text, fingerprint))
            with self.assertRaises(a.AuthorityIntegrityError):
                self.store.get_operating_operation("approve", limits=LIMITS)
            connection.execute("UPDATE submissions SET request_json=?,fingerprint=? WHERE submission_id='approve'", original)
        original_role = connection.execute("SELECT relationship FROM record_links WHERE record_id=? AND ordinal=0", (identity,)).fetchone()[0]
        connection.execute("UPDATE record_links SET relationship=? WHERE record_id=? AND ordinal=0", ("X" * 100000, identity))
        with patch("research_pipeline.operating_authority_store._canonical_json", side_effect=AssertionError("prohibited reconstruction")):
            with self.assertRaises(a.AuthorityLimitError):
                self.store.get_operating_operation("approve", limits=replace(LIMITS, max_record_bytes=50000))
        connection.execute("UPDATE record_links SET relationship=? WHERE record_id=? AND ordinal=0", (original_role, identity))
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DELETE FROM revisions WHERE record_id=? AND revision=1", (identity,))
        with self.assertRaises(a.AuthorityIntegrityError):
            self.inspect()

    def test_recovery_membership_and_links_precede_request_decoding(self):
        """Public recovery rejects actual membership/link corruption before parsing any saved JSON."""
        _, _, _, signed, original = self.approve()
        identity = signed.to_dict()["decision"]["decision_id"]
        connection = self.store._connection
        # Save complete rows and restore each mutation outside the public API's
        # own transaction. Foreign keys are disabled only to create corrupt links.
        connection.execute("PRAGMA foreign_keys=OFF")
        corruptions = [
            ("revisions", "UPDATE revisions SET submission_id='short-note',ordinal=99 WHERE record_id=?", (identity,)),
            ("revisions", "UPDATE revisions SET submission_id='approve',ordinal=99 WHERE record_id='project'", ()),
            ("revisions", "UPDATE revisions SET ordinal=9 WHERE record_id=?", (identity,)),
            ("revisions", "UPDATE revisions SET ordinal='invalid' WHERE record_id=?", (identity,)),
            ("record_links", "UPDATE record_links SET relationship=? WHERE record_id=? AND ordinal=0", (b"blob", identity)),
            ("record_links", "UPDATE record_links SET target_revision='invalid' WHERE record_id=? AND ordinal=0", (identity,)),
            ("record_links", "UPDATE record_links SET ordinal=900 WHERE record_id=? AND ordinal=0", (identity,)),
            ("record_links", "UPDATE record_links SET ordinal='invalid' WHERE record_id=? AND ordinal=0", (identity,)),
            ("audit_events", "UPDATE audit_events SET provenance_json=? WHERE submission_id='approve'", (b"blob",)),
        ]
        try:
            for table, sql, parameters in corruptions:
                with self.subTest(sql=sql):
                    cursor = connection.execute("SELECT rowid,* FROM " + table)
                    names = [item[0] for item in cursor.description][1:]
                    rows = cursor.fetchall()
                    try:
                        connection.execute(sql, parameters)
                        with patch("research_pipeline.operating_authority_store._canonical_json",
                                   side_effect=AssertionError("request/content reconstruction before preflight")), \
                                self.assertRaises(a.AuthorityIntegrityError):
                            self.store.get_operating_operation("approve", limits=LIMITS)
                    finally:
                        connection.executemany("UPDATE " + table + " SET " +
                            ",".join(name + "=?" for name in names) + " WHERE rowid=?",
                            [(*row[1:], row[0]) for row in rows])
        finally:
            connection.execute("PRAGMA foreign_keys=ON")
        count = sum(connection.execute("SELECT count(*) FROM " + table +
            " WHERE record_id=? AND revision=1", (identity,)).fetchone()[0]
            for table in ("record_links", "artifact_links"))
        with patch("research_pipeline.operating_authority_store._canonical_json",
                   side_effect=AssertionError("request decoding before reference allowance")), \
                self.assertRaises(a.AuthorityLimitError):
            self.store.get_operating_operation("approve", limits=replace(LIMITS, max_references=count - 1))
        self.assertEqual(self.store.get_operating_operation("approve",
            limits=replace(LIMITS, max_references=count)), original)

    def test_recovery_reserves_requests_receipts_and_results_before_construction(self):
        """Check request limits and inject later receipt exhaustion only after real reconstruction.

        The request reservation is the natural peak, so a global threshold cannot
        isolate the receipt boundary. A test-only charge there exercises the real
        retained-metadata limit at equality and one byte below the needed allowance.
        """
        from research_pipeline import operating_authority_store as module
        _, _, _, _, original = self.approve()
        request_size = self.store._connection.execute(
            "SELECT length(CAST(request_json AS BLOB)) FROM submissions WHERE submission_id='approve'").fetchone()[0]
        reservations, result_boundaries = [], []
        reserve = module._Reader.reserve
        make_result = module._result

        def observe_result(envelope, receipt):
            """Observe the real result boundary without substituting validation or stored metadata."""
            result_boundaries.append(len(reservations))
            return make_result(envelope, receipt)

        def observe(reader, size):
            """Delegate every real allowance check and record its canonical-byte threshold."""
            reservations.append((reader.metadata_bytes, size))
            return reserve(reader, size)

        with patch.object(module._Reader, "reserve", observe), patch.object(module, "_result", observe_result):
            self.assertEqual(self.store.get_operating_operation("approve", limits=LIMITS), original)
        self.assertEqual(result_boundaries, [len(reservations)])
        # Raw request plus fingerprint and four separately constructed request
        # representations are reserved together, using the measured canonical size.
        request_index = next(i for i, (_, size) in enumerate(reservations) if size == 5 * request_size + 64)
        before, charged = reservations[request_index]
        threshold = before + charged
        self.assertEqual(threshold, max(start + size for start, size in reservations))
        self.assertGreater(before + request_size + 64, request_size)
        self.assertLess(before + request_size + 64, threshold - 1)
        for sentinel in ("_canonical_json", "Submission.from_dict", "authority.decode_envelope"):
            with self.subTest(sentinel=sentinel), patch(
                    "research_pipeline.operating_authority_store." + sentinel,
                    side_effect=AssertionError("request reconstructed before retention reservation")), \
                    self.assertRaises(a.AuthorityLimitError):
                self.store.get_operating_operation("approve", limits=replace(LIMITS, max_metadata_bytes=threshold - 1))
        self.assertEqual(self.store.get_operating_operation("approve",
            limits=replace(LIMITS, max_metadata_bytes=threshold)), original)
        # Receipt and result have a separate final preconstruction reservation,
        # independent of their eventual output cap.
        receipt_index = result_boundaries[0] - 1
        receipt_before, receipt_charge = reservations[receipt_index]
        self.assertGreater(receipt_charge, len(a.canonical(original.to_dict())))
        reconstruct_request = a.submission
        read_envelope = module._Reader.read
        make_receipt = module.SubmissionReceipt
        decision_reference = original.to_dict()["decision"]
        decision_key = decision_reference["record_id"], decision_reference["revision"]
        for extra_byte in (1, 0):
            completed = {"request": False, "envelope": False}
            observed_reservations, target_attempts = [], []

            def observe_request(signed):
                """Mark derived-request reconstruction only after the real constructor succeeds."""
                submitted = reconstruct_request(signed)
                completed["request"] = True
                return submitted

            def observe_envelope(reader, key):
                """Mark actual decision reconstruction only after the real bounded read succeeds."""
                envelope = read_envelope(reader, key)
                self.assertEqual(key, decision_key)
                completed["envelope"] = True
                return envelope

            def charge_at_receipt(reader, size):
                """Simulate retained metadata at the observed receipt boundary using real reservations."""
                index = len(observed_reservations)
                incoming = reader.metadata_bytes, size
                observed_reservations.append(incoming)
                self.assertEqual(incoming, reservations[index])
                if index == receipt_index:
                    self.assertEqual(incoming, (receipt_before, receipt_charge))
                    self.assertTrue(completed["request"])
                    self.assertTrue(completed["envelope"])
                    target_attempts.append(incoming)
                    additional = reader.limits.max_metadata_bytes - reader.metadata_bytes - size + extra_byte
                    self.assertGreaterEqual(additional, 0)
                    reserve(reader, additional)
                    self.assertEqual(reader.limits.max_metadata_bytes - reader.metadata_bytes, size - extra_byte)
                return reserve(reader, size)

            receipt_effect = AssertionError("receipt constructed before allowance") if extra_byte else make_receipt
            result_effect = AssertionError("result constructed before allowance") if extra_byte else make_result
            with self.subTest(extra_byte=extra_byte), \
                    patch.object(a, "submission", observe_request), \
                    patch.object(module._Reader, "read", observe_envelope), \
                    patch.object(module._Reader, "reserve", charge_at_receipt), \
                    patch.object(module, "SubmissionReceipt", side_effect=receipt_effect) as receipt_constructor, \
                    patch.object(module, "_result", side_effect=result_effect) as result_constructor:
                if extra_byte:
                    with self.assertRaises(a.AuthorityLimitError):
                        self.store.get_operating_operation("approve", limits=LIMITS)
                else:
                    self.assertEqual(self.store.get_operating_operation("approve", limits=LIMITS), original)
                self.assertTrue(completed["request"])
                self.assertTrue(completed["envelope"])
                self.assertEqual(target_attempts, [(receipt_before, receipt_charge)])
                self.assertEqual(receipt_constructor.call_count, 0 if extra_byte else 1)
                self.assertEqual(result_constructor.call_count, 0 if extra_byte else 1)
        result_size = len(a.canonical(original.to_dict()))
        with self.assertRaisesRegex(a.AuthorityLimitError, "detached result byte limit"):
            self.store.get_operating_operation("approve", limits=replace(LIMITS, max_result_bytes=result_size - 1))
        self.assertEqual(self.store.get_operating_operation("approve",
            limits=replace(LIMITS, max_result_bytes=result_size)), original)

    def test_recovery_cached_envelope_does_not_certify_membership_or_audit(self):
        """History's preloaded envelope cannot suppress original submission/audit preflight checks."""
        from research_pipeline import operating_authority_store as module
        _, _, _, signed, _ = self.approve()
        identity = signed.to_dict()["decision"]["decision_id"]
        read = module._Reader.read

        for sql, parameters in (
                ("UPDATE audit_events SET provenance_json=? WHERE submission_id='approve'", (b"blob",)),
                ("UPDATE revisions SET ordinal=99 WHERE record_id=?", (identity,))):
            def cached(reader, key):
                """Read the real envelope, then damage independently checked operation metadata."""
                envelope = read(reader, key)
                if key == (identity, 1):
                    reader.connection.execute(sql, parameters)
                return envelope

            with self.subTest(sql=sql), patch.object(module._Reader, "read", cached), \
                    self.assertRaises(a.AuthorityIntegrityError):
                self.store.inspect_operating_history("synthetic", "project", policy=None, limits=LIMITS)


class OperatingRetentionSizeTests(unittest.TestCase):
    """Check canonical arithmetic and generated audit bounds without filesystem access."""

    def test_fragment_framing_and_scalar_escaping(self):
        """Nested populated/empty fragments preserve nulls, punctuation and ASCII JSON escape lengths."""
        from research_pipeline import operating_authority_store as module
        from tests.test_operating_authority import binding
        fragments = [binding().to_dict(), {}, [], [None, False, True, 2**63 - 1],
            {"café": ['A "quoted" line\n', "résumé.md", "𝄞", {"nested": []}], "absent": None}]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                self.assertEqual(module._fragment_bytes(fragment), len(a.canonical(fragment)))

    def test_fresh_receipt_bounds_cover_both_retained_representations(self):
        """The largest generated event ID reaches equality; shorter IDs release only their overhead."""
        from research_pipeline import operating_authority_store as module
        from research_pipeline.domain import SubmissionReceipt
        from tests.test_operating_authority import binding
        envelope = a.encode_envelope(sign(decision(binding(), scope())))
        key = envelope.record_id, envelope.revision
        planned = module._receipt_result_bytes(key, "approve", 19, 29,
            len(a.canonical(envelope.provenance.to_dict())))
        for event_id in (1, 2**63 - 1):
            receipt = SubmissionReceipt("approve", "a" * 64, event_id, TIME, envelope.provenance, (key,))
            result = module._result(envelope, receipt)
            actual = len(a.canonical(receipt.to_dict())) + len(a.canonical(result.to_dict()))
            self.assertEqual(planned - actual, 2 * (19 - len(str(event_id))))
