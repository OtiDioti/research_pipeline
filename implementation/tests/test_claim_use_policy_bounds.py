"""Shallow policy resolution, independent accounts, temporal bounds and corrupt metadata rejection."""

from contextlib import contextmanager, ExitStack
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
from research_pipeline import store as store_module, operating_authority
from research_pipeline.backup import create_backup, restore_backup, inspect_backup, BackupError
from research_pipeline.claim_use import ClaimUseLimitError, ClaimUseIntegrityError, encode_envelope as use_envelope
from research_pipeline.domain import RecordEnvelope
from research_pipeline.scientific import Claim, Justification, encode_envelope
from research_pipeline.snapshot import RootSelector, SnapshotSelection
from research_pipeline.store import RecordStore, StoreLayoutError, ReferenceResolutionError, RecordNotFoundError
from tests.claim_use_fixtures import populate, binding, batch, ref, review, assessment_envelope, PROVENANCE, LIMITS
from tests.test_claim_use_store import metadata
from tests.test_claim_use_policy import policy_record
from tests.snapshot_fixtures import limits as snapshot_limits


@contextmanager
def policy_dispatch_guard():
    """Reject any classification/codec call for a Decision while allowing real graph decoding.

    AssertionError cannot be swallowed as an ordinary malformed-codec diagnostic.
    Yield spies so isolated policy tests also prove that no dispatch was attempted.
    Patches are process-local and restored before each independent test returns.
    """
    targets = ((store_module, "_classification"), (store_module, "_decode_typed_envelope"),
               (operating_authority, "decode_envelope"))
    with ExitStack() as stack:
        spies = []
        for module, name in targets:
            original = getattr(module, name)

            def checked(envelope, *args, _original=original, **kwargs):
                """Permit legitimate non-policy reads and fail immediately on a Decision."""
                if envelope.kind == "decision":
                    raise AssertionError("policy Decision reached typed dispatch")
                return _original(envelope, *args, **kwargs)

            spies.append(stack.enter_context(patch.object(module, name, side_effect=checked)))
        yield spies


class PolicyBoundsTests(unittest.TestCase):
    """Finite accounts reject whole real operations, without modifying public ceilings or runners."""

    def setUp(self):
        """Create per-test private stores and deterministic setup-only graph fixtures."""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent/"store"
        self.store = RecordStore.create(self.root, schema_version=5)
        self.addCleanup(self.store.close)
        populate(self.store)

    def test_independent_write_account_equality_and_overflow(self):
        """Each measured dimension accepts equality and rejects one-unit deficit without SQL effects."""
        request = batch("advance", [policy_record()])
        before = metadata(self.root)
        with self.store._transaction() as connection:
            counts = freshness.prepare(self.store, connection, request).reader.counts
        self.assertGreater(counts["policy_revisions"], 2, "prospective-root resolutions count independently")
        for dimension in ("policy_revisions", "index_rows", "bindings", "records", "references", "transitions", "causes", "metadata_bytes"):
            with self.subTest(dimension=dimension):
                with patch.object(freshness, "WRITE_LIMITS", {**freshness.WRITE_LIMITS, dimension: counts[dimension]-1}):
                    with self.assertRaisesRegex(ClaimUseLimitError, dimension):
                        self.store.submit(request)
                self.assertEqual(metadata(self.root), before)
                with self.store._transaction() as connection, patch.object(freshness, "WRITE_LIMITS", {
                        **freshness.WRITE_LIMITS, dimension: counts[dimension]}):
                    freshness.prepare(self.store, connection, request)
        self.store.submit(request)
        self.assertEqual(self.store.inspect_claim_use("use", limits=LIMITS).to_dict()["generation"], 2)

    def test_distinct_policy_resolution_has_separate_cache_independent_account(self):
        """Repeated exact policy reads share revision count while assertion counts remain independent."""
        self.store.submit(batch("p2", [policy_record()]))
        with self.store._transaction() as connection:
            reader = freshness.Reader(self.store, connection)
            reader.caps["policy_revisions"] = 1
            self.assertEqual(reader.policy(("policy", 1)), {})
            self.assertEqual(reader.policy(("policy", 1)), {})
            self.assertEqual(reader.counts["policy_revisions"], 1)
            self.assertEqual(reader.counts["assertion_revisions"], 0)
            with self.assertRaisesRegex(ClaimUseLimitError, "policy_revisions"):
                reader.policy(("policy", 2))

    def test_marked_shallow_policies_never_dispatch_in_stored_proposed_or_overlay_reads(self):
        """Recognized markers stay exact JSON in every policy view, with one parse per revision."""
        for marker in ("operating_authority", "scientific"):
            content = dict(format=f"research_pipeline.{marker}_content", version=1,
                           declaration="Shallow only", favorable=True)
            envelope = RecordEnvelope(f"marked-{marker}", 1, "decision", content, PROVENANCE,
                                      [ref("manifest", "declaration", "work_product_manifest")])
            key = envelope.record_id, envelope.revision
            self.store.submit(batch(f"save-{marker}", [envelope]))
            for mode in ("stored", "proposed", "overlay"):
                with self.subTest(marker=marker, mode=mode), self.store._transaction() as connection:
                    aggregate = freshness.Reader(self.store, connection)
                    plan = freshness.Plan(aggregate, "prospective")
                    reader = freshness.Reader(self.store, connection,
                        () if mode == "stored" else [envelope],
                        overlay=plan if mode == "overlay" else None,
                        aggregate=aggregate if mode == "overlay" else None)
                    reader.caps["policy_revisions"] = 1
                    reader.caps["assertion_revisions"] = 0
                    with policy_dispatch_guard() as spies, \
                            patch.object(freshness, "_strict_json", wraps=freshness._strict_json) as parse, \
                            patch.object(RecordEnvelope, "from_dict", wraps=RecordEnvelope.from_dict) as rebuild:
                        self.assertEqual(reader.policy(key), content)
                        self.assertEqual(reader.policy(key), content)
                    for spy in spies:
                        spy.assert_not_called()
                    parse.assert_called_once_with(envelope._content_json)
                    rebuild.assert_called_once()
                    self.assertEqual(reader.cache[key], envelope)
                    self.assertEqual(reader.counts["policy_revisions"], 1)
                    self.assertEqual(reader.counts["assertion_revisions"], 0)
                    self.assertEqual(reader.counts["records"], 1)
                    self.assertEqual(reader.counts["references"], 3)  # one link and two resolutions
                    if mode == "overlay":
                        second = freshness.Reader(self.store, connection, [envelope], overlay=plan, aggregate=aggregate)
                        with policy_dispatch_guard():
                            self.assertEqual(second.policy(key), content)
                        self.assertEqual(aggregate.counts["policy_revisions"], 2)
                        self.assertEqual(aggregate.counts["records"], 1)
                        self.assertEqual(aggregate.counts["assertion_revisions"], 0)
                        self.assertEqual(aggregate.counts["references"], 5)

    def test_public_marked_policy_advancement_matches_prospective_and_stored_inspection(self):
        """A marked generic successor advances once without policy decoding in either graph view."""
        before = self.store.inspect_claim_use("use", limits=LIMITS).to_dict()
        declaration = dict(format="research_pipeline.operating_authority_content", version=1,
                           declaration="Attributed only", favorable=True)
        envelope = RecordEnvelope("policy", 2, "decision", declaration, PROVENANCE)
        request = batch("marked-policy-advance", [envelope])
        prospective = []
        original = freshness._inspection

        def capture(reader, identity, limits):
            """Retain actual prospective use observations while exercising normal graph validation."""
            result = original(reader, identity, limits)
            if reader.overlay is not None and identity == "use":
                prospective.append(result.to_dict())
            return result

        with policy_dispatch_guard(), patch.object(freshness, "_inspection", side_effect=capture):
            receipt = self.store.submit(request)
            current = self.store.inspect_claim_use("use", limits=LIMITS).to_dict()
            self.assertEqual(self.store.submit(request), receipt)
            self.assertEqual(self.store.inspect_claim_use("use", limits=LIMITS).to_dict(), current)
        self.assertEqual(len(prospective), 1)
        self.assertEqual(prospective[0]["observed_policies"], current["observed_policies"])
        expected = dict(binding=dict(record_id="use", revision=1, target_kind="promotion_eligibility"),
                        dependency_ordinal=26,
                        bound_policy=dict(record_id="policy", revision=1, target_kind="decision"),
                        observed_policy=dict(record_id="policy", revision=2, target_kind="decision"),
                        observed_content=declaration, attributed=True, superseded=True)
        self.assertEqual(current["observed_policies"], [expected])
        for view in (prospective[0], current):
            self.assertEqual(view["generation"], before["generation"] + 1)
            self.assertFalse(view["eligible"])
            self.assertFalse(view["authorized_disposition"]["available"])
            self.assertTrue(view["requires_reassessment"])
            self.assertEqual(view["limitations"], before["limitations"])
            self.assertEqual(view["historical_pins"], before["historical_pins"])
            self.assertEqual(len(view["mechanical_freshness"]["last_transition"]["causes"]), 1)
        self.assertEqual(len(self.store.claim_use_history("use", limits=LIMITS).to_dict()["transitions"]), 2)

    def test_cached_policy_scratch_reserves_local_and_aggregate_budgets_before_validation(self):
        """One-byte scratch deficits fail before parsing/round-trip; exact reservations suffice."""
        envelope = policy_record()
        self.store.submit(batch("scratch-policy", [envelope]))
        key = "policy", 2
        scratch = 6 * len(envelope._content_json)
        for account in ("local", "aggregate"):
            for deficit in (1, 0):
                with self.subTest(account=account, deficit=deficit), self.store._transaction() as connection:
                    aggregate = freshness.Reader(self.store, connection)
                    reader = freshness.Reader(self.store, connection, aggregate=aggregate)
                    reader.read(key, classify=False)
                    target = reader if account == "local" else aggregate
                    target.caps["metadata_bytes"] = target.counts["metadata_bytes"] + scratch - deficit
                    if deficit:
                        with patch.object(freshness, "_strict_json", side_effect=AssertionError("unreserved parse")), \
                                patch.object(freshness, "_canonical", side_effect=AssertionError("unreserved encoding")), \
                                patch.object(RecordEnvelope, "to_dict", side_effect=AssertionError("unreserved serialization")), \
                                patch.object(RecordEnvelope, "from_dict", side_effect=AssertionError("unreserved round-trip")):
                            with self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes"):
                                reader.policy(key)
                        self.assertNotIn(key, reader.policy_values)
                    else:
                        self.assertEqual(reader.policy(key), envelope.content)
                        self.assertEqual(reader.policy(key), envelope.content)
                        self.assertEqual(target.counts["metadata_bytes"], target.caps["metadata_bytes"])
                    self.assertEqual(reader.counts["policy_revisions"], 1)
                    self.assertEqual(aggregate.counts["policy_revisions"], 1)
                    self.assertEqual(reader.counts["assertion_revisions"], 0)

    def test_metadata_only_stored_preflight_honors_local_and_aggregate_remaining_bytes(self):
        """Insufficient reconstruction budgets reject before fetching JSON or rebuilding envelopes."""
        for account in ("local", "aggregate"):
            with self.subTest(account=account), self.store._transaction() as connection:
                aggregate = freshness.Reader(self.store, connection)
                reader = freshness.Reader(self.store, connection, aggregate=aggregate)
                target = reader if account == "local" else aggregate
                target.caps["metadata_bytes"] = target.counts["metadata_bytes"]
                statements = []
                connection.set_trace_callback(statements.append)
                try:
                    with patch.object(store_module, "_strict_json", side_effect=AssertionError("unreserved JSON")), \
                            patch.object(self.store, "_metadata_envelope", side_effect=AssertionError("unreserved envelope")):
                        with self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes"):
                            reader.policy(("policy", 1))
                finally:
                    connection.set_trace_callback(None)
                self.assertFalse(any(sql.startswith("SELECT r.content_json,r.provenance_json") for sql in statements))

    def test_default_snapshot_and_legacy_reader_keep_classification(self):
        """Metadata-only entries stay private while default capture and schema-4 reads still classify."""
        envelope = RecordEnvelope("marked", 1, "decision",
            dict(format="research_pipeline.operating_authority_content", version=1), PROVENANCE)
        with RecordStore.create(self.parent/"legacy", schema_version=4) as legacy:
            legacy.submit(batch("snapshot-input", [envelope, RecordEnvelope("project", 1, "project", {}, PROVENANCE)]))
            with legacy._transaction() as connection:
                limits = snapshot_limits()
                with policy_dispatch_guard() as spies:
                    record, entry, _, _ = legacy._snapshot_record(connection, ("marked", 1), limits,
                        limits.max_metadata_bytes, limits.max_references, _classify=False)
                self.assertEqual(record, envelope)
                self.assertNotIn("classification", entry)
                for spy in spies:
                    spy.assert_not_called()
                with patch.object(store_module, "_classification", wraps=store_module._classification) as classify, \
                        patch.object(store_module, "_decode_typed_envelope", wraps=store_module._decode_typed_envelope) as decode, \
                        patch.object(operating_authority, "decode_envelope", wraps=operating_authority.decode_envelope) as operating:
                    self.assertEqual(freshness.Reader(legacy, connection).read(("marked", 1)), envelope)
                classify.assert_called_once()
                decode.assert_called_once_with(envelope)
                operating.assert_called_once_with(envelope)
            with patch.object(store_module, "_classification", wraps=store_module._classification) as classify:
                snapshot = legacy.capture_snapshot(SnapshotSelection(RootSelector("project", 1),
                    [RootSelector("marked", 1)]), limits=snapshot_limits())
            self.assertEqual(classify.call_count, 2)
            entries = {entry["record_id"]: entry for entry in snapshot.records}
            self.assertEqual(entries["project"]["classification"]["category"], "generic")
            self.assertEqual(entries["marked"]["classification"]["category"], "malformed_typed")
            self.assertEqual(entries["marked"]["classification"]["diagnostic"], "local_codec_failure")

    def test_hard_policy_revision_ceiling_accepts_1024_distinct_and_rejects_1025(self):
        """The independent fixed ceiling resolves 1,024 real Decisions without assertion work."""
        self.store.submit(batch("many-decisions", [policy_record(f"declaration-{i}", 1) for i in range(1024)]))
        with self.store._transaction() as connection:
            reader = freshness.Reader(self.store, connection)
            for i in range(1024):
                reader.policy((f"declaration-{i}", 1))
            self.assertEqual(reader.counts["policy_revisions"], 1024)
            self.assertEqual(reader.counts["assertion_revisions"], 0)
            with self.assertRaisesRegex(ClaimUseLimitError, "policy_revisions"):
                reader.policy(("policy", 1))

    def test_hard_transition_ceiling_accepts_128_and_rolls_back_129(self):
        """A real policy event updates all 128 current uses and refuses incomplete impact at 129."""
        self.store.submit_typed(batch("independent-candidates", [encode_envelope(f"candidate-{i}", 1,
            Claim(str(i), "synthetic", [], ref("scope", "context", "research_context"), [], [], []), PROVENANCE)
            for i in range(125)]))
        for start in range(0, 125, 16):
            self.store.submit_typed(batch(f"many-{start}", [use_envelope(f"many-{i}", 1,
                binding(f"candidate-{i}", (), (), ()), PROVENANCE)
                for i in range(start, min(start+16, 125))]))
        self.store.submit(batch("p2", [policy_record()]))
        rows = self.store._connection.execute("SELECT count(*) FROM claim_use_current WHERE generation=2").fetchone()[0]
        self.assertEqual(rows, 128)
        self.store.submit_typed(batch("extra", [use_envelope("extra", 1, binding("unrelated", (), (), ()), PROVENANCE)]))
        before = metadata(self.root)
        with self.assertRaisesRegex(ClaimUseLimitError, "transitions"):
            self.store.submit(batch("p3", [policy_record(revision=3)]))
        self.assertEqual(metadata(self.root), before)

    def test_inspection_result_and_metadata_independent_limits(self):
        """Complete policy observations honor public result/processing bounds without truncation."""
        self.store.submit(batch("p2", [policy_record(text="x"*2000)]))
        view = self.store.inspect_claim_use("use", limits=LIMITS)
        size = len(view._json)
        self.assertEqual(self.store.inspect_claim_use("use", limits=replace(LIMITS, max_result_bytes=size)), view)
        with self.assertRaisesRegex(ClaimUseLimitError, "result_bytes"):
            self.store.inspect_claim_use("use", limits=replace(LIMITS, max_result_bytes=size-1))
        with self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes"):
            self.store.inspect_claim_use("use", limits=replace(LIMITS, max_metadata_bytes=100))

    def test_complete_prospective_policy_result_overflow_rolls_back_before_insertion(self):
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
                self.store.submit(batch("large-observed-policy", [policy_record(text="x"*300000)]))
        self.assertFalse(any(call.args == ("before_metadata",) for call in seam.call_args_list))
        self.assertEqual(metadata(self.root), before)

    def test_policy_watch_preflight_seeks_temporal_index_before_payload(self):
        """Exact policy equality and event-range ordering exclude later rows before bounded fetching."""
        self.store.submit(batch("p2", [policy_record()]))
        event = self.store.get_submission("p2").event_id
        statements = []
        connection = self.store._connection
        connection.set_trace_callback(statements.append)
        try:
            with self.store._transaction() as owned:
                freshness.prepare(self.store, owned, batch("p2", [policy_record()]), cutoff=event, verify=False)
        finally:
            connection.set_trace_callback(None)
        probes = [sql for sql in statements if "FROM claim_use_dependencies d INDEXED BY claim_use_dependency_watch" in sql]
        self.assertTrue(any("typeof(" in sql for sql in probes))
        self.assertTrue(any("typeof(" not in sql for sql in probes))
        for sql in probes:
            self.assertIn("d.target_id='policy'", sql)
            self.assertIn("d.target_kind='decision'", sql)
            self.assertIn("d.role='policy_declared'", sql)
            self.assertIn(f"d.registration_event<{event}", sql)
            self.assertIn("ORDER BY d.registration_event,d.use_id,d.binding_revision,d.ordinal", sql)
            plan = " ".join(row[-1] for row in connection.execute("EXPLAIN QUERY PLAN " + sql))
            self.assertIn("claim_use_dependency_watch", plan)
            self.assertIn("registration_event<?", plan)
            self.assertNotIn("TEMP B-TREE", plan)

    def test_later_policy_and_registration_history_do_not_charge_earlier_event(self):
        """Replay reads only the preceding head and pre-event watches, never lifetime policy history."""
        request = batch("p2", [policy_record()])
        receipt = self.store.submit(request)
        with self.store._transaction() as connection:
            expected = freshness.prepare(self.store, connection, request, cutoff=receipt.event_id, verify=False)
        for revision in range(3, 9):
            self.store.submit(batch(f"p{revision}", [policy_record(revision=revision)]))
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
            self.store.submit(batch("overflow-generation", [policy_record()]))
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
        """Policy resolution cannot silently omit damaged JSON, wrong-kind or absent required pins."""
        for identity in ("candidate", "missing"):
            wrong = replace(binding("unrelated", (), (), ()), policies=[ref(identity, "authorization_policy", "decision")])
            before = metadata(self.root)
            with self.assertRaises((ReferenceResolutionError, RecordNotFoundError)):
                self.store.submit_typed(batch("wrong-"+identity, [use_envelope("wrong-"+identity, 1, wrong, PROVENANCE)]))
            self.assertEqual(metadata(self.root), before)
        connection = self.store._connection
        connection.execute("UPDATE revisions SET content_json='not JSON' WHERE record_id='policy'")
        before = metadata(self.root)
        with self.assertRaises((ClaimUseIntegrityError, ReferenceResolutionError)):
            self.store.submit(batch("broken", [policy_record()]))
        self.assertEqual(metadata(self.root), before)
        with self.assertRaises((ClaimUseIntegrityError, ReferenceResolutionError)):
            self.store.inspect_claim_use("use", limits=LIMITS)

    def test_metadata_only_policies_retain_json_envelope_and_ordered_link_validation(self):
        """Damaged exact metadata fails shallow reads and public writes without changing any table."""
        envelope = RecordEnvelope("policy", 2, "decision",
            dict(format="research_pipeline.scientific_content", version=1), PROVENANCE,
            [ref("manifest", "declaration", "work_product_manifest"), ref("scope", "context", "research_context")])
        self.store.submit(batch("linked-policy", [envelope]))
        connection = self.store._connection
        provenance = connection.execute(
            "SELECT provenance_json FROM revisions WHERE record_id='policy' AND revision=2").fetchone()[0]
        changes = [
            ("content_json", "not JSON", envelope._content_json),
            ("content_json", '{"a": 1}', envelope._content_json),
            ("content_json", '{"a":1,"a":2}', envelope._content_json),
            ("content_json", '[]', envelope._content_json),
            ("provenance_json", '{}', provenance),
            ("operational_status", "ready", None),
            ("scientific_disposition", "provisional", None),
        ]
        request = batch("must-rollback", [policy_record(revision=3)])
        # Each fixture restores its isolated damage, so later cases see the same
        # valid history; the controller's schema and validation are untouched.
        for column, damaged, original in [*changes, ("ordinal", 2, 0)]:
            table = "record_links" if column == "ordinal" else "revisions"
            predicate = "record_id='policy' AND revision=2" + (" AND target_id='manifest'" if column == "ordinal" else "")
            with self.subTest(column=column, damaged=damaged):
                connection.execute(f"UPDATE {table} SET {column}=? WHERE {predicate}", (damaged,))
                try:
                    before = metadata(self.root)
                    with policy_dispatch_guard():
                        with self.store._transaction() as owned:
                            with self.assertRaises(ClaimUseIntegrityError):
                                freshness.Reader(self.store, owned).policy(("policy", 2))
                        with self.assertRaises((ClaimUseIntegrityError, ReferenceResolutionError)):
                            self.store.submit(request)
                        with self.assertRaises((ClaimUseIntegrityError, ReferenceResolutionError)):
                            self.store.inspect_claim_use("use", limits=LIMITS)
                    self.assertEqual(metadata(self.root), before)
                finally:
                    connection.execute(f"UPDATE {table} SET {column}=? WHERE {predicate}", (original,))
        with self.store._transaction() as owned, policy_dispatch_guard():
            for key, error in ((("candidate", 1), ReferenceResolutionError), (("missing", 1), RecordNotFoundError)):
                with self.subTest(key=key), self.assertRaises(error):
                    freshness.Reader(self.store, owned).policy(key)

    def test_rehashed_backups_reject_policy_origin_dependency_temporal_and_transition_damage(self):
        """Rehashing corrupted snapshots never substitutes for chronological policy integrity."""
        self.store.submit(batch("advance", [policy_record()]))
        create_backup(self.store, self.parent/"backup")
        changes = (
            "DELETE FROM claim_use_policy_origin",
            "UPDATE claim_use_policy_origin SET event_watermark=1",
            "UPDATE claim_use_dependencies SET role='assessment_declared' WHERE role='policy_declared' AND use_id='use'",
            "UPDATE claim_use_dependencies SET registration_event=4 WHERE use_id='use'",
            "UPDATE claim_use_revision_events SET event_id=1 WHERE record_id='policy' AND revision=2",
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
        """Later large unrelated Decisions cannot exhaust schema-5 activation-boundary accounts."""
        with RecordStore.create(self.parent/"old", schema_version=4) as old:
            populate(old)
            old.submit(batch("old-p2", [policy_record()]))
            create_backup(old, self.parent/"old-backup")
        with restore_backup(self.parent/"old-backup", self.parent/"migrated", target_schema=5,
                migration_provenance=PROVENANCE) as store:
            # Required policy lifetime metadata exceeds one record collectively,
            # but only bound and exact observed heads are resolved per event.
            for revision in range(3, 9):
                store.submit(batch(f"policy-{revision}", [policy_record(revision=revision, text="x"*20000)]))
                store.submit_typed(batch(f"register-{revision}", [use_envelope(f"later-{revision}", 1,
                    binding("unrelated", (), (), ()), PROVENANCE)]))
            checkpoint = []
            original = freshness._inspection
            def capture(reader, identity, limits):
                """Observe boundary-only policy heads through the real independent inspection."""
                result = original(reader, identity, limits)
                if reader.cutoff == 5 and reader.overlay is None:
                    checkpoint.append(result.to_dict())
                return result
            with patch.object(freshness, "_inspection", capture):
                with RecordStore.open(self.parent/"migrated"):
                    pass
            self.assertTrue(checkpoint)
            self.assertTrue(all(p["observed_policy"]["revision"] == 2 for v in checkpoint for p in v["observed_policies"]))

    def test_near_ceiling_schema5_registration_survives_replay(self):
        """A large accepted binding survives independent reopen and verified backup checks."""
        value = replace(binding("premise-a", (), (), ()), limitations=["z"*1030000])
        request = batch("large-register", [use_envelope("large", 1, value, PROVENANCE)])
        receipt = self.store.submit_typed(request)
        view = self.store.inspect_claim_use("large", limits=LIMITS)
        with RecordStore.open(self.root) as store:
            self.assertEqual(store.inspect_claim_use("large", limits=LIMITS), view)
            self.assertEqual(store.submit_typed(request), receipt)
            create_backup(store, self.parent/"large-backup")
        self.assertEqual(inspect_backup(self.parent/"large-backup").schema_version, 5)


if __name__ == "__main__":
    unittest.main()
