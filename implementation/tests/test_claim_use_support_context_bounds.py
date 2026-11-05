"""Independent schema-7 finite accounts, indexed ranges, corruption and atomic rejection."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import claim_use_store as freshness, scientific
from research_pipeline.claim_use import ClaimUseLimitError, ClaimUseIntegrityError, encode_envelope as use_envelope
from research_pipeline.domain import RecordEnvelope
from research_pipeline.store import RecordStore, ReferenceResolutionError, StoreLayoutError
from tests.claim_use_fixtures import support_context_graph, batch, ref, binding, PROVENANCE, LIMITS
from tests.test_claim_use_context import context_record
from tests.test_claim_use_store import metadata


class SupportContextBoundsTests(unittest.TestCase):
    """Every test owns real SQLite state; damaged rows are restored before the next subcase."""

    def setUp(self):
        """Allocate private metadata, artifacts and independently selected support scopes."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=7)
        self.addCleanup(self.store.close)
        self.fixture = support_context_graph(self.store)

    def test_operation_accounts_accept_equality_and_reject_one_unit_deficits(self):
        """Actual complete write accounts, including repeated roots, are independently enforced before writes."""
        request = batch("advance", [context_record("support-evidence")])
        before = metadata(self.root)
        with self.store._transaction() as connection:
            counts = dict(freshness.prepare(self.store, connection, request).reader.counts)
        self.assertEqual(counts["context_observations"], 22)  # U:9; D:4+historical U:9.
        for dimension in ("context_revisions", "context_observations", "references", "index_rows", "causes",
                          "transitions", "metadata_bytes", "records", "bindings"):
            with self.subTest(dimension=dimension):
                with patch.object(freshness, "WRITE_LIMITS", {**freshness.WRITE_LIMITS, dimension: counts[dimension]-1}):
                    with self.assertRaisesRegex(ClaimUseLimitError, dimension):
                        self.store.submit(request)
                self.assertEqual(metadata(self.root), before)
                with self.store._transaction() as connection, patch.object(freshness, "WRITE_LIMITS", {
                        **freshness.WRITE_LIMITS, dimension: counts[dimension]}):
                    actual = freshness.prepare(self.store, connection, request)
                self.assertEqual(actual.reader.counts, counts)

    def test_shared_target_and_support_observations_charge_together(self):
        """A cached scope occurrence still consumes output and reference work on every visit."""
        with self.store._transaction() as connection:
            reader = freshness.Reader(self.store, connection, limits=LIMITS)
            freshness._inspection(reader, "use", LIMITS)
            self.assertEqual(reader.counts["context_observations"], 9)
            reader = freshness.Reader(self.store, connection, limits=LIMITS)
            reader.caps["context_observations"] = 8
            with self.assertRaisesRegex(ClaimUseLimitError, "context_observations"):
                freshness._inspection(reader, "use", LIMITS)
            reader = freshness.Reader(self.store, connection)
            value = reader.context(("support-evidence", 1))
            count = reader.counts["references"]
            reader.caps["references"] = count+1
            self.assertEqual(reader.context(("support-evidence", 1)), value)
            with self.assertRaisesRegex(ClaimUseLimitError, "references"):
                reader.context(("support-evidence", 1))

    def test_required_scope_codec_reserves_local_and_aggregate_scratch(self):
        """Independent codec scratch is checked before decoding, even when typed reconstruction is cached."""
        for account in ("local", "aggregate"):
            for deficit in (0, 1):
                with self.subTest(account=account, deficit=deficit), self.store._transaction() as connection:
                    aggregate = freshness.Reader(self.store, connection)
                    reader = freshness.Reader(self.store, connection, aggregate=aggregate)
                    key = "support-evidence", 1
                    envelope = reader.read(key, classify=False)
                    target = reader if account == "local" else aggregate
                    target.caps["metadata_bytes"] = target.counts["metadata_bytes"]+6*len(envelope._content_json)-deficit
                    with patch.object(scientific, "decode_envelope", wraps=scientific.decode_envelope) as decode:
                        if deficit:
                            with self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes"):
                                reader.context(key)
                            decode.assert_not_called()
                        else:
                            self.assertEqual(reader.context(key).to_dict(), envelope.content)
                            decode.assert_called_once()

    def test_watch_scalar_payload_ranges_seek_identity_and_event_without_sort(self):
        """Both preflight and payload queries use the exact temporal watch index prefix and full suffix."""
        request = batch("advance", [context_record("support-evidence")])
        receipt = self.store.submit(request)
        statements = []
        connection = self.store._connection
        connection.set_trace_callback(statements.append)
        try:
            with self.store._transaction() as owned:
                freshness.prepare(self.store, owned, request, cutoff=receipt.event_id, verify=False)
        finally:
            connection.set_trace_callback(None)
        queries = [q for q in statements if "FROM claim_use_support_contexts INDEXED BY claim_use_support_context_watch" in q]
        self.assertTrue(any("typeof(" in q for q in queries))
        self.assertTrue(any("typeof(" not in q for q in queries))
        for query in queries:
            self.assertIn("context_id='support-evidence'", query)
            self.assertIn(f"registration_event<{receipt.event_id}", query)
            self.assertIn("ORDER BY registration_event,use_id,binding_revision,ordinal", query)
            plan = " ".join(row[-1] for row in connection.execute("EXPLAIN QUERY PLAN "+query))
            self.assertIn("context_id=? AND registration_event<?", plan)
            self.assertNotIn("TEMP B-TREE", plan)

    def test_later_history_and_unrelated_contexts_do_not_change_earlier_accounts(self):
        """Temporal accounts are unchanged by later registrations and watched/unwatched revisions."""
        request = batch("advance", [context_record("support-evidence")])
        receipt = self.store.submit(request)
        with self.store._transaction() as connection:
            expected = freshness.prepare(self.store, connection, request, cutoff=receipt.event_id, verify=False)
        for revision in range(3, 6):
            self.store.submit(batch("later-"+str(revision), [context_record("support-evidence", revision)]))
            self.store.submit_typed(batch("new-use-"+str(revision), [use_envelope("late-"+str(revision), 1,
                self.fixture["independent"], PROVENANCE)]))
        with self.store._transaction() as connection:
            actual = freshness.prepare(self.store, connection, request, cutoff=receipt.event_id, verify=False)
        self.assertEqual(actual.transitions, expected.transitions)
        self.assertEqual(actual.reader.counts, expected.reader.counts)
        with self.store._transaction() as connection:
            first = freshness.prepare(self.store, connection, batch("unwatched", [context_record("excluded-input")]))
        self.store.submit(batch("more-unwatched", [context_record("unwatched-"+str(i), 1) for i in range(40)]))
        with self.store._transaction() as connection:
            second = freshness.prepare(self.store, connection, batch("unwatched", [context_record("excluded-input")]))
        self.assertEqual(first.reader.counts, second.reader.counts)
        self.assertEqual(second.transitions, {})
        with RecordStore.open(self.root):
            pass

    def test_projection_and_origin_damage_rejected_by_inspection_or_open(self):
        """Missing, extra, reordered, substituted and orphan occurrences cannot masquerade as provenance."""
        connection = self.store._connection
        changes = (
            ("claim_use_support_contexts", "DELETE FROM claim_use_support_contexts WHERE use_id='use' AND ordinal=4"),
            ("claim_use_support_contexts", "UPDATE claim_use_support_contexts SET context_id='support-route-a' WHERE use_id='use' AND ordinal=4"),
            ("claim_use_support_contexts", "UPDATE claim_use_support_contexts SET source_id='s-premise-b' WHERE use_id='use' AND ordinal=2"),
            ("claim_use_support_contexts", "UPDATE claim_use_support_contexts SET registration_event=1 WHERE use_id='use'"),
            ("claim_use_support_contexts", "UPDATE claim_use_support_contexts SET ordinal=20 WHERE use_id='use' AND ordinal=7"),
            ("claim_use_support_contexts", "INSERT INTO claim_use_support_contexts SELECT 'orphan',binding_revision,ordinal,source_id,source_revision,source_kind,source_role,route_ordinal,premise_ordinal,evidence_ordinal,context_id,context_revision,registration_event FROM claim_use_support_contexts WHERE use_id='use' AND ordinal=0"),
            ("claim_use_support_context_origin", "DELETE FROM claim_use_support_context_origin"),
            ("claim_use_support_context_origin", "UPDATE claim_use_support_context_origin SET event_watermark=1"),
        )
        for table, sql in changes:
            with self.subTest(sql=sql):
                before = metadata(self.root)
                connection.execute("PRAGMA foreign_keys=OFF")
                connection.execute(sql)
                connection.execute("PRAGMA foreign_keys=ON")
                try:
                    with self.assertRaises((StoreLayoutError, ClaimUseIntegrityError)):
                        RecordStore.open(self.root)
                    if "orphan" not in sql:
                        with self.assertRaises((ClaimUseIntegrityError, ReferenceResolutionError)):
                            self.store.inspect_claim_use("use", limits=LIMITS)
                finally:
                    connection.execute("PRAGMA foreign_keys=OFF")
                    connection.execute("DELETE FROM "+table)
                    for row in before[table]:
                        connection.execute("INSERT INTO "+table+" VALUES ("+",".join("?" for _ in row)+")", row)
                    connection.execute("PRAGMA foreign_keys=ON")

    def test_malformed_required_metadata_and_transition_corruption_fail_closed(self):
        """Every selected scope requires complete canonical supported metadata and exact persisted causes."""
        connection = self.store._connection
        original = connection.execute("SELECT content_json FROM revisions WHERE record_id='support-evidence'").fetchone()[0]
        for text in ("{}", "not JSON", original.replace('"version":1', '"version":9'), original.replace('{', '{ ', 1)):
            connection.execute("UPDATE revisions SET content_json=? WHERE record_id='support-evidence'", (text,))
            try:
                before = metadata(self.root)
                with self.assertRaises((ReferenceResolutionError, ClaimUseIntegrityError)):
                    self.store.submit(batch("bad", [context_record("support-evidence")]))
                self.assertEqual(metadata(self.root), before)
            finally:
                connection.execute("UPDATE revisions SET content_json=? WHERE record_id='support-evidence'", (original,))
        self.store.submit(batch("advance", [context_record("support-evidence")]))
        connection.execute("UPDATE claim_use_generations SET causes_json='[]' WHERE use_id='use' AND generation=2")
        with self.assertRaises((StoreLayoutError, ClaimUseIntegrityError)):
            RecordStore.open(self.root)

    def test_generation_and_event_exhaustion_without_affected_uses_are_atomic(self):
        """Signed maximum rejects generation changes and generic no-impact writes, preserving all metadata."""
        connection = self.store._connection
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("UPDATE claim_use_current SET generation=? WHERE use_id='use'", (2**63-1,))
        connection.execute("PRAGMA foreign_keys=ON")
        before = metadata(self.root)
        with self.assertRaisesRegex(ClaimUseLimitError, "generation"):
            self.store.submit(batch("overflow", [context_record("support-evidence")]))
        self.assertEqual(metadata(self.root), before)
        connection.execute("UPDATE claim_use_current SET generation=1 WHERE use_id='use'")
        self.store.submit(batch("ceiling", [RecordEnvelope("ceiling", 1, "event", {}, PROVENANCE)]))
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("UPDATE audit_events SET event_id=? WHERE submission_id='ceiling'", (2**63-1,))
        connection.execute("UPDATE claim_use_revision_events SET event_id=? WHERE record_id='ceiling'", (2**63-1,))
        connection.execute("PRAGMA foreign_keys=ON")
        before = metadata(self.root)
        with self.assertRaisesRegex(ClaimUseLimitError, "event_id"):
            self.store.submit(batch("no-impact", [RecordEnvelope("never", 1, "event", {}, PROVENANCE)]))
        self.assertEqual(metadata(self.root), before)

    def test_complete_result_limit_and_prospective_overflow_before_insertion(self):
        """Repeated full support scope contents cannot be truncated to admit an oversized complete view."""
        view = self.store.inspect_claim_use("use", limits=LIMITS)
        self.assertEqual(self.store.inspect_claim_use("use", limits=replace(LIMITS, max_result_bytes=len(view._json))), view)
        with self.assertRaisesRegex(ClaimUseLimitError, "result_bytes"):
            self.store.inspect_claim_use("use", limits=replace(LIMITS, max_result_bytes=len(view._json)-1))
        with RecordStore.create(self.parent/"shared", schema_version=7) as shared:
            fixture = support_context_graph(shared, shared=True)
            downstream = replace(fixture["downstream"], routes=[replace(fixture["downstream"].routes[0], premises=[
                replace(fixture["downstream"].routes[0].premises[0],
                    upstream_use=ref("a-forward-use", "premise_use", "promotion_eligibility"))])])
            before = metadata(self.parent/"shared")
            # Eight complete observed contents alone exceed 4 MiB. Depending on
            # earlier retained work, the independent scratch ceiling can reject
            # first; either failure must precede all metadata insertion.
            with patch("research_pipeline.store._fault") as seam:
                with self.assertRaisesRegex(ClaimUseLimitError, "result_bytes|metadata_bytes"):
                    shared.submit(batch("large", [use_envelope("a-forward-down", 1, downstream, PROVENANCE),
                        use_envelope("a-forward-use", 1, fixture["upstream"], PROVENANCE),
                        context_record("support-shared", question="x"*600000)]))
            self.assertFalse(any(c.args == ("before_metadata",) for c in seam.call_args_list))
            self.assertEqual(metadata(self.parent/"shared"), before)

    def test_hard_context_resolution_and_transition_ceiling(self):
        """Actual schema-7 operations retain the 1,024 revision and 128 transition hard ceilings."""
        self.store.submit(batch("contexts", [context_record("finite-"+str(i), 1) for i in range(1024)]))
        with self.store._transaction() as connection:
            reader = freshness.Reader(self.store, connection)
            for i in range(1024):
                reader.context(("finite-"+str(i), 1))
            self.assertEqual(reader.counts["context_revisions"], 1024)
            with self.assertRaisesRegex(ClaimUseLimitError, "context_revisions"):
                reader.context(("support-evidence", 1))
        from research_pipeline.scientific import Claim, encode_envelope
        self.store.submit_typed(batch("many-candidates", [encode_envelope("many-candidate-"+str(i), 1,
            Claim(str(i), "synthetic", [], ref("independent-scope", "context", "research_context"), [], [], []), PROVENANCE)
            for i in range(127)]))
        for start in range(0, 127, 16):
            self.store.submit_typed(batch("many-"+str(start), [use_envelope("many-"+str(i), 1,
                replace(self.fixture["independent"], candidate_claim=ref("many-candidate-"+str(i), "candidate_claim", "claim")),
                PROVENANCE) for i in range(start, min(start+16, 127))]))
        self.store.submit(batch("advance-many", [context_record("independent-scope")]))
        self.assertEqual(self.store._connection.execute("SELECT count(*) FROM claim_use_current WHERE generation=2").fetchone()[0], 128)
        self.store.submit_typed(batch("extra", [use_envelope("extra", 1, self.fixture["independent"], PROVENANCE)]))
        before = metadata(self.root)
        with self.assertRaisesRegex(ClaimUseLimitError, "transitions"):
            self.store.submit(batch("too-many", [context_record("independent-scope", 3)]))
        self.assertEqual(metadata(self.root), before)

    def test_hard_512_combined_occurrences_and_activation_deficit(self):
        """A real 512-occurrence view fits; its 513th selected occurrence rejects activation without publication."""
        from research_pipeline.backup import create_backup, restore_backup, BackupError
        from research_pipeline.claim_use import ClaimUsePremise, ClaimUseRoute
        from research_pipeline.scientific import Claim, Evidence, Justification, encode_envelope
        from tests.claim_use_fixtures import review, assessment_envelope
        for extra in (False, True):
            oldroot = self.parent/("boundary-old-"+str(extra))
            with RecordStore.create(oldroot, schema_version=6) as old:
                fixture = support_context_graph(old, uses=False)
                context = ref("support-target", "context", "research_context")
                records = [encode_envelope("boundary-candidate", 1, Claim("candidate", "synthetic", [], context, [], [], []), PROVENANCE)]
                records.extend(encode_envelope("boundary-evidence-"+str(i), 1,
                    Evidence([fixture["artifact"]], context, "property", [], "method", [], [], [], "unverified", [], [], "synthetic"), PROVENANCE)
                    for i in range(84+int(extra)))
                routes = []
                for i in range(6):
                    identity = "boundary-route-"+str(i)
                    premises = []
                    # Candidate + six routes + 504 Evidence + target = 512 observations.
                    evidence_count = 84+(int(extra) if i == 5 else 0)
                    records.extend([encode_envelope(identity, 1, Justification(context, premises, [], "method",
                        [ref("boundary-candidate", "conclusion", "claim")],
                        [ref("boundary-evidence-"+str(j), "evidence", "evidence") for j in range(evidence_count)], []), PROVENANCE),
                        assessment_envelope(identity+"-review", 1, review("boundary-candidate", identity, "support-target"), PROVENANCE)])
                    routes.append(ClaimUseRoute(ref(identity, "support_route", "justification"),
                        [ClaimUsePremise(p, None) for p in premises], [ref(identity+"-review", "support_assessment", "review")]))
                old.submit_typed(batch("boundary-science", records))
                value = replace(binding("boundary-candidate", (), (), ()), target_context=ref("support-target", "target_context", "research_context"), routes=routes)
                old.submit_typed(batch("boundary-register", [use_envelope("boundary", 1, value, PROVENANCE)]))
                backup = self.parent/("boundary-backup-"+str(extra))
                create_backup(old, backup)
                before = metadata(oldroot)
            destination = self.parent/("boundary-seven-"+str(extra))
            if extra:
                with self.assertRaisesRegex(BackupError, "context_observations"):
                    restore_backup(backup, destination, target_schema=7, migration_provenance=PROVENANCE)
                self.assertTrue((destination/".restore-incomplete").exists())
            else:
                with restore_backup(backup, destination, target_schema=7, migration_provenance=PROVENANCE) as store:
                    view = store.inspect_claim_use("boundary", limits=LIMITS).to_dict()
                    self.assertEqual(len(view["observed_support_contexts"]), 511)
                    self.assertEqual(len(view["observed_target_contexts"]), 1)
            self.assertEqual(metadata(oldroot), before)
