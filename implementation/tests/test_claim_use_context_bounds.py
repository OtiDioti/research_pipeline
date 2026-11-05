"""Exact context resolution, independent fixed accounts, temporal indexed work and corruption rejection."""

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import claim_use_store as freshness
from research_pipeline import store as store_module, scientific
from research_pipeline.backup import create_backup, restore_backup, inspect_backup, BackupError
from research_pipeline.claim_use import ClaimUseLimitError, ClaimUseIntegrityError, encode_envelope as use_envelope
from research_pipeline.domain import RecordEnvelope
from research_pipeline.scientific import Claim, Justification, encode_envelope
from research_pipeline.store import RecordStore, ReferenceResolutionError, RecordNotFoundError
from tests.claim_use_fixtures import populate, binding, batch, ref, review, assessment_envelope, PROVENANCE, LIMITS
from tests.test_claim_use_store import metadata
from tests.test_claim_use_context import context_record


def successor(revision=2, text="Prose-only successor"):
    """Advance the fixture's explicit target scope with coherent scientific metadata."""
    return context_record("scope", revision, question=text)


@contextmanager
def context_dispatch_guard():
    """Fail if context-only resolution takes generic classification instead of its explicit codec."""
    original = store_module._classification
    def checked(envelope, *args, **kwargs):
        """Allow normal graph classification while rejecting redundant scope dispatch."""
        if envelope.kind == "research_context":
            raise AssertionError("context-only read reached classification")
        return original(envelope, *args, **kwargs)
    with patch.object(store_module, "_classification", checked):
        yield


class ContextBoundsTests(unittest.TestCase):
    """Reject incomplete real operations atomically using independent bounded accounts."""

    def setUp(self):
        """Give every test its own store, paths and setup-only exact graph."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=6)
        self.addCleanup(self.store.close)
        populate(self.store)

    def test_independent_write_account_equality_and_deficit(self):
        """Each actual admission dimension accepts equality and fails a one-unit deficit atomically."""
        request = batch("advance", [successor()])
        before = metadata(self.root)
        with self.store._transaction() as connection:
            counts = freshness.prepare(self.store, connection, request).reader.counts
        self.assertGreater(counts["context_revisions"], 2)
        self.assertEqual(counts["context_observations"], 4)  # U, D plus its historical U, independent.
        for dimension in ("context_revisions", "context_observations", "index_rows", "bindings", "records",
                          "references", "transitions", "causes", "metadata_bytes"):
            with self.subTest(dimension=dimension):
                with patch.object(freshness, "WRITE_LIMITS", {**freshness.WRITE_LIMITS, dimension: counts[dimension]-1}):
                    with self.assertRaisesRegex(ClaimUseLimitError, dimension):
                        self.store.submit(request)
                self.assertEqual(metadata(self.root), before)
                with self.store._transaction() as connection, patch.object(freshness, "WRITE_LIMITS", {
                        **freshness.WRITE_LIMITS, dimension: counts[dimension]}):
                    accepted = freshness.prepare(self.store, connection, request)
                self.assertEqual(accepted.reader.counts, counts)
        self.assertEqual(dict(freshness.WRITE_LIMITS)["context_observations"], 512)
        self.assertEqual(metadata(self.root), before)

    def test_exact_resolver_classification_bypass_cache_and_aggregate_accounts(self):
        """Only the explicit scientific decoder resolves extra scope reads, with independent root charges."""
        key = "scope", 1
        with self.store._transaction() as connection:
            aggregate = freshness.Reader(self.store, connection)
            for _ in range(2):
                reader = freshness.Reader(self.store, connection, aggregate=aggregate)
                with context_dispatch_guard(), patch.object(scientific, "decode_envelope", wraps=scientific.decode_envelope) as decode:
                    value = reader.context(key)
                    self.assertEqual(reader.context(key), value)
                decode.assert_called_once()
                self.assertEqual(reader.counts["context_revisions"], 1)
                self.assertEqual(reader.counts["policy_revisions"], 0)
                self.assertEqual(reader.counts["assertion_revisions"], 0)
            self.assertEqual(aggregate.counts["context_revisions"], 2)
            self.assertEqual(aggregate.counts["records"], 1)

    def test_context_codec_scratch_precedes_decoder_in_local_and_aggregate_accounts(self):
        """A single-byte codec scratch deficit fails before decoding, even after reconstruction is cached."""
        key = "scope", 1
        for account in ("local", "aggregate"):
            for deficit in (0, 1):
                with self.subTest(account=account, deficit=deficit), self.store._transaction() as connection:
                    aggregate = freshness.Reader(self.store, connection)
                    reader = freshness.Reader(self.store, connection, aggregate=aggregate)
                    envelope = reader.read(key, classify=False)
                    target = reader if account == "local" else aggregate
                    target.caps["metadata_bytes"] = target.counts["metadata_bytes"] + 6*len(envelope._content_json)-deficit
                    with patch.object(scientific, "decode_envelope", wraps=scientific.decode_envelope) as decode:
                        if deficit:
                            with self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes"):
                                reader.context(key)
                            decode.assert_not_called()
                            self.assertNotIn(key, reader.context_values)
                        else:
                            self.assertEqual(reader.context(key).to_dict(), envelope.content)
                            decode.assert_called_once()

    def test_context_codec_scratch_after_independent_typed_resolution(self):
        """A prior typed decode cannot pay for another context codec's protected allocation."""
        from research_pipeline.scientific import ResearchContext
        for account in ("local", "aggregate"):
            for deficit in (0, 1):
                with self.subTest(account=account, deficit=deficit), self.store._transaction() as connection:
                    aggregate = freshness.Reader(self.store, connection)
                    reader = freshness.Reader(self.store, connection, aggregate=aggregate)
                    expected = reader.typed(ref("scope", "context", "research_context"), ResearchContext)
                    envelope = reader.read(("scope", 1), classify=False)
                    target = reader if account == "local" else aggregate
                    target.caps["metadata_bytes"] = target.counts["metadata_bytes"] + 6*len(envelope._content_json)-deficit
                    with patch.object(scientific, "decode_envelope", wraps=scientific.decode_envelope) as decode:
                        if deficit:
                            with self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes"):
                                reader.context(("scope", 1))
                            decode.assert_not_called()
                        else:
                            self.assertEqual(reader.context(("scope", 1)), expected)
                            decode.assert_called_once()

    def test_cached_context_occurrences_still_charge_references(self):
        """Semantic caching saves decoding while every incoming occurrence keeps its own work charge."""
        with self.store._transaction() as connection:
            reader = freshness.Reader(self.store, connection)
            expected = reader.context(("scope", 1))
            count = reader.counts["references"]
            reader.caps["references"] = count + 1
            self.assertEqual(reader.context(("scope", 1)), expected)
            self.assertEqual(reader.counts["references"], count + 1)
            self.assertEqual(reader.counts["context_revisions"], 1)
            with self.assertRaisesRegex(ClaimUseLimitError, "references"):
                reader.context(("scope", 1))

    def test_required_context_metadata_and_projection_fail_closed(self):
        """Unsupported, malformed, noncanonical and incoherent exact scopes cannot hide impact."""
        connection = self.store._connection
        original = connection.execute("SELECT content_json FROM revisions WHERE record_id='scope'").fetchone()[0]
        invalid = ("{}", "not JSON", '{"a":1,"a":2}', original.replace('"version":1', '"version":2'),
                   original.replace('{', '{ ', 1))
        for text in invalid:
            with self.subTest(text=text[:40]):
                connection.execute("UPDATE revisions SET content_json=? WHERE record_id='scope'", (text,))
                try:
                    before = metadata(self.root)
                    with self.assertRaises((ReferenceResolutionError, ClaimUseIntegrityError)):
                        self.store.submit(batch("broken-context", [successor()]))
                    self.assertEqual(metadata(self.root), before)
                    with self.assertRaises((ReferenceResolutionError, ClaimUseIntegrityError)):
                        self.store.inspect_claim_use("use", limits=LIMITS)
                finally:
                    connection.execute("UPDATE revisions SET content_json=? WHERE record_id='scope'", (original,))
        # A syntactically valid extra projection is still incoherent scientific scope.
        connection.execute("INSERT INTO record_links VALUES ('scope',1,0,'unexpected','candidate',1,'claim')")
        with self.assertRaises((ReferenceResolutionError, ClaimUseIntegrityError)):
            self.store.submit(batch("bad-context-projection", [successor()]))

    def test_hard_context_revision_ceiling_accepts_1024_distinct_and_rejects_1025(self):
        """The independent fixed ceiling resolves 1,024 real ResearchContexts without assertion work."""
        self.store.submit(batch("many-contexts", [context_record(f"declaration-{i}", 1) for i in range(1024)]))
        with self.store._transaction() as connection:
            reader = freshness.Reader(self.store, connection)
            for i in range(1024):
                reader.context((f"declaration-{i}", 1))
            self.assertEqual(reader.counts["context_revisions"], 1024)
            self.assertEqual(reader.counts["assertion_revisions"], 0)
            with self.assertRaisesRegex(ClaimUseLimitError, "context_revisions"):
                reader.context(("scope", 1))

    def test_hard_transition_ceiling_accepts_128_and_rolls_back_129(self):
        """A real context event updates all 128 current uses and refuses incomplete impact at 129."""
        self.store.submit_typed(batch("independent-candidates", [encode_envelope(f"candidate-{i}", 1,
            Claim(str(i), "synthetic", [], ref("scope", "context", "research_context"), [], [], []), PROVENANCE)
            for i in range(125)]))
        for start in range(0, 125, 16):
            self.store.submit_typed(batch(f"many-{start}", [use_envelope(f"many-{i}", 1,
                binding(f"candidate-{i}", (), (), ()), PROVENANCE)
                for i in range(start, min(start+16, 125))]))
        self.store.submit(batch("p2", [successor()]))
        rows = self.store._connection.execute("SELECT count(*) FROM claim_use_current WHERE generation=2").fetchone()[0]
        self.assertEqual(rows, 128)
        self.store.submit_typed(batch("extra", [use_envelope("extra", 1, binding("unrelated", (), (), ()), PROVENANCE)]))
        before = metadata(self.root)
        with self.assertRaisesRegex(ClaimUseLimitError, "transitions"):
            self.store.submit(batch("p3", [successor(revision=3)]))
        self.assertEqual(metadata(self.root), before)

    def test_inspection_result_and_metadata_independent_limits(self):
        """Complete context observations honor public result/processing bounds without truncation."""
        self.store.submit(batch("p2", [successor(text="x"*2000)]))
        view = self.store.inspect_claim_use("use", limits=LIMITS)
        size = len(view._json)
        self.assertEqual(self.store.inspect_claim_use("use", limits=replace(LIMITS, max_result_bytes=size)), view)
        with self.assertRaisesRegex(ClaimUseLimitError, "result_bytes"):
            self.store.inspect_claim_use("use", limits=replace(LIMITS, max_result_bytes=size-1))
        with self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes"):
            self.store.inspect_claim_use("use", limits=replace(LIMITS, max_metadata_bytes=100))

    def test_complete_prospective_context_result_overflow_rolls_back_before_insertion(self):
        """Repeated historical occurrences can exceed the complete 4 MiB view without one large record."""
        records = [encode_envelope(f"node-{i}", 1,
            Claim(str(i), "synthetic", [], ref("scope", "context", "research_context"), [], [], []), PROVENANCE)
            for i in range(15)]
        for i in range(1, 15):
            route = Justification(ref("scope", "context", "research_context"),
                [ref(f"node-{i-1}", "premise", "claim")], [], "Recorded chain",
                [ref(f"node-{i}", "conclusion", "claim")], [], [])
            records.extend([encode_envelope(f"chain-route-{i}", 1, route, PROVENANCE),
                assessment_envelope(f"chain-review-{i}", 1, review(f"node-{i}", f"chain-route-{i}"), PROVENANCE)])
        self.store.submit_typed(batch("chain-science", records))
        for i in range(15):
            identity = "a-root" if i == 14 else f"chain-{i}"
            value = binding(f"node-{i}", (), (), ()) if i == 0 else binding(f"node-{i}",
                (f"chain-route-{i}",), (f"chain-review-{i}",), (f"node-{i-1}",), f"chain-{i-1}")
            self.store.submit_typed(batch(f"chain-register-{i}", [use_envelope(identity, 1, value, PROVENANCE)]))
        before = metadata(self.root)
        with patch("research_pipeline.store._fault") as seam:
            with self.assertRaisesRegex(ClaimUseLimitError, "result_bytes"):
                self.store.submit(batch("large-observed-context", [successor(text="x"*300000)]))
        self.assertFalse(any(call.args == ("before_metadata",) for call in seam.call_args_list))
        self.assertEqual(metadata(self.root), before)

    def test_context_watch_preflight_seeks_temporal_index_before_payload(self):
        """Exact context equality and event-range ordering exclude later rows before bounded fetching."""
        self.store.submit(batch("p2", [successor()]))
        event = self.store.get_submission("p2").event_id
        statements = []
        connection = self.store._connection
        connection.set_trace_callback(statements.append)
        try:
            with self.store._transaction() as owned:
                freshness.prepare(self.store, owned, batch("p2", [successor()]), cutoff=event, verify=False)
        finally:
            connection.set_trace_callback(None)
        probes = [sql for sql in statements if "FROM claim_use_dependencies d INDEXED BY claim_use_dependency_watch" in sql]
        self.assertTrue(any("typeof(" in sql for sql in probes))
        self.assertTrue(any("typeof(" not in sql for sql in probes))
        for sql in probes:
            self.assertIn("d.target_id='scope'", sql)
            self.assertIn("d.target_kind='research_context'", sql)
            self.assertIn("d.role='context'", sql)
            self.assertIn(f"d.registration_event<{event}", sql)
            self.assertIn("ORDER BY d.registration_event,d.use_id,d.binding_revision,d.ordinal", sql)
            plan = " ".join(row[-1] for row in connection.execute("EXPLAIN QUERY PLAN " + sql))
            self.assertIn("claim_use_dependency_watch", plan)
            self.assertIn("registration_event<?", plan)
            self.assertNotIn("TEMP B-TREE", plan)

    def test_later_context_and_registration_history_do_not_charge_earlier_event(self):
        """Replay reads only the preceding head and pre-event watches, never lifetime context history."""
        request = batch("p2", [successor()])
        receipt = self.store.submit(request)
        with self.store._transaction() as connection:
            expected = freshness.prepare(self.store, connection, request, cutoff=receipt.event_id, verify=False)
        for revision in range(3, 9):
            self.store.submit(batch(f"p{revision}", [successor(revision=revision)]))
            self.store.submit_typed(batch(f"late-{revision}", [use_envelope(f"late-{revision}", 1,
                binding("unrelated", (), (), ()), PROVENANCE)]))
        with self.store._transaction() as connection:
            actual = freshness.prepare(self.store, connection, request, cutoff=receipt.event_id, verify=False)
        self.assertEqual(actual.transitions, expected.transitions)
        self.assertEqual(actual.reader.counts, expected.reader.counts)
        with RecordStore.open(self.root):
            pass

    def test_generation_and_scientific_event_exhaustion_are_atomic(self):
        """Generation overflow and SQLite's max-ROWID fallback never admit partial or backward events."""
        connection = self.store._connection
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("UPDATE claim_use_current SET generation=? WHERE use_id='use'", (2**63-1,))
        connection.execute("PRAGMA foreign_keys=ON")
        before = metadata(self.root)
        with self.assertRaisesRegex(ClaimUseLimitError, "generation"):
            self.store.submit(batch("overflow-generation", [successor()]))
        self.assertEqual(metadata(self.root), before)
        connection.execute("UPDATE claim_use_current SET generation=1 WHERE use_id='use'")
        self.store.submit(batch("ceiling-seed", [RecordEnvelope("ceiling", 1, "event", {}, PROVENANCE)]))
        # This isolated fixture moves an otherwise unreferenced scientific event
        # and its navigation row to the actual signed maximum, without weakening
        # ordinary admission or using a fake allocator.
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("UPDATE audit_events SET event_id=? WHERE submission_id='ceiling-seed'", (2**63-1,))
        connection.execute("UPDATE claim_use_revision_events SET event_id=? WHERE record_id='ceiling'", (2**63-1,))
        connection.execute("PRAGMA foreign_keys=ON")
        before = metadata(self.root)
        with self.assertRaisesRegex(ClaimUseLimitError, "event_id"):
            self.store.submit(batch("overflow-event", [RecordEnvelope("never", 1, "event", {}, PROVENANCE)]))
        self.assertEqual(metadata(self.root), before)

    def test_malformed_wrong_kind_missing_required_targets_fail_explicitly(self):
        """Context resolution cannot silently omit damaged JSON, wrong-kind or absent required pins."""
        for identity in ("candidate", "missing"):
            wrong = replace(binding("unrelated", (), (), ()), target_context=ref(identity, "target_context", "research_context"))
            before = metadata(self.root)
            with self.assertRaises((ReferenceResolutionError, RecordNotFoundError)):
                self.store.submit_typed(batch("wrong-"+identity, [use_envelope("wrong-"+identity, 1, wrong, PROVENANCE)]))
            self.assertEqual(metadata(self.root), before)
        connection = self.store._connection
        connection.execute("UPDATE revisions SET content_json='not JSON' WHERE record_id='scope'")
        before = metadata(self.root)
        with self.assertRaises((ClaimUseIntegrityError, ReferenceResolutionError)):
            self.store.submit(batch("broken", [successor()]))
        self.assertEqual(metadata(self.root), before)
        with self.assertRaises((ClaimUseIntegrityError, ReferenceResolutionError)):
            self.store.inspect_claim_use("use", limits=LIMITS)

    def test_open_rejects_missing_extra_wrong_context_transitions_and_origin(self):
        """Reopen recomputes exact context effects and rejects valid-SQL damage without repairing it."""
        self.store.submit(batch("advance", [successor()]))
        connection = self.store._connection
        changes = (
            ("claim_use_context_origin", "DELETE FROM claim_use_context_origin"),
            ("claim_use_context_origin", "UPDATE claim_use_context_origin SET event_watermark=1"),
            ("claim_use_dependencies", "UPDATE claim_use_dependencies SET role='route_context' WHERE use_id='use' AND role='context'"),
            ("claim_use_generations", "DELETE FROM claim_use_generations WHERE use_id='use' AND generation=2"),
            ("claim_use_generations", "UPDATE claim_use_generations SET causes_json='[]' WHERE use_id='use' AND generation=2"),
            ("claim_use_generations", "INSERT INTO claim_use_generations SELECT use_id,3,binding_revision,'scientific',(SELECT event_id FROM audit_events WHERE submission_id='scientific'),status,causes_json FROM claim_use_generations WHERE use_id='use' AND generation=2"),
        )
        from research_pipeline.store import StoreLayoutError
        for table, sql in changes:
            before = metadata(self.root)
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute(sql)
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                damaged = metadata(self.root)
                with self.subTest(sql=sql), self.assertRaises(StoreLayoutError):
                    RecordStore.open(self.root)
                self.assertEqual(metadata(self.root), damaged)
            finally:
                # Restore only this disposable fixture's damage; production has no
                # repair path and open must leave every inconsistent row untouched.
                connection.execute("PRAGMA foreign_keys=OFF")
                connection.execute(f"DELETE FROM {table}")
                for row in before[table]:
                    connection.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in row)})", row)
                connection.execute("PRAGMA foreign_keys=ON")

    def test_rehashed_backups_reject_context_origin_dependency_temporal_and_transition_damage(self):
        """Rehashing corrupted snapshots never substitutes for chronological context integrity."""
        self.store.submit(batch("advance", [successor()]))
        create_backup(self.store, self.parent/"backup")
        changes = (
            "DELETE FROM claim_use_context_origin",
            "UPDATE claim_use_context_origin SET event_watermark=1",
            "UPDATE claim_use_dependencies SET role='assessment_declared' WHERE role='context' AND use_id='use'",
            "UPDATE claim_use_dependencies SET registration_event=4 WHERE use_id='use'",
            "UPDATE claim_use_revision_events SET event_id=1 WHERE record_id='scope' AND revision=2",
            "DELETE FROM claim_use_generations WHERE use_id='use' AND generation=2",
            "UPDATE claim_use_generations SET causes_json='[]' WHERE use_id='use' AND generation=2",
            "UPDATE claim_use_upstreams SET upstream_revision=2 WHERE use_id='downstream-use'",
        )
        for index, sql in enumerate(changes):
            target = self.parent/f"bad-{index}"
            shutil.copytree(self.parent/"backup", target)
            database = target/"snapshot.sqlite3"
            database.chmod(0o600)
            with sqlite3.connect(database) as connection:
                connection.execute(sql)
            database.chmod(0o400)
            path = target/"manifest.json"
            document = json.loads(path.read_text())
            data = database.read_bytes()
            document["metadata"] = dict(digest=hashlib.sha256(data).hexdigest(), size=len(data))
            path.chmod(0o600)
            path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")))
            path.chmod(0o400)
            with self.subTest(sql=sql), self.assertRaises(BackupError):
                inspect_backup(target)

    def test_migration_activation_accounts_exclude_later_history(self):
        """Later large unrelated ResearchContexts cannot exhaust schema-6 activation-boundary accounts."""
        with RecordStore.create(self.parent/"old", schema_version=5) as old:
            populate(old)
            old.submit(batch("old-p2", [successor()]))
            create_backup(old, self.parent/"old-backup")
        with restore_backup(self.parent/"old-backup", self.parent/"migrated", target_schema=6,
                migration_provenance=PROVENANCE) as store:
            # Required context lifetime metadata exceeds one record collectively,
            # but only bound and exact observed heads are resolved per event.
            for revision in range(3, 9):
                store.submit(batch(f"context-{revision}", [successor(revision=revision, text="x"*20000)]))
                store.submit_typed(batch(f"register-{revision}", [use_envelope(f"later-{revision}", 1,
                    binding("unrelated", (), (), ()), PROVENANCE)]))
            checkpoint = []
            original = freshness._inspection
            def capture(reader, identity, limits):
                """Observe boundary-only context heads through the real independent inspection."""
                result = original(reader, identity, limits)
                if reader.cutoff == 5 and reader.overlay is None:
                    checkpoint.append(result.to_dict())
                return result
            with patch.object(freshness, "_inspection", capture):
                with RecordStore.open(self.parent/"migrated"):
                    pass
            self.assertTrue(checkpoint)
            self.assertTrue(all(p["observed_context"]["revision"] == 2 for v in checkpoint for p in v["observed_target_contexts"]))



if __name__ == "__main__":
    unittest.main()
