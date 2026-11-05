"""Independent public write preflight witnesses and exact transition-bound behavior."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline.claim_use import ClaimUseLimitError, encode_envelope as use_envelope
from research_pipeline.domain import ArtifactReference, RecordEnvelope
from research_pipeline.store import RecordStore
from tests.claim_use_fixtures import populate, binding, batch, review, ref, PROVENANCE, LIMITS, assessment_envelope
from tests.test_claim_use_store import metadata


class HostileRetainedValue:
    """Record any accidental dispatch of an unchecked caller-owned value."""

    def __init__(self):
        """Keep hook observations private to this fixture instance."""
        self.calls = []

    def __iter__(self):
        """Fail on unchecked iteration."""
        self.calls.append("iteration")
        raise AssertionError("hostile iterator invoked")

    def __eq__(self, other):
        """Fail on unchecked equality comparisons."""
        self.calls.append("equality")
        raise AssertionError("hostile equality invoked")

    def __len__(self):
        """Fail on unchecked length measurement."""
        self.calls.append("length")
        raise AssertionError("hostile length invoked")

    def __str__(self):
        """Fail on unchecked scalar conversion."""
        self.calls.append("conversion")
        raise AssertionError("hostile conversion invoked")

    def __hash__(self):
        """Fail on unchecked identity/cache hashing."""
        self.calls.append("hash")
        raise AssertionError("hostile hash invoked")

    def to_dict(self):
        """Fail on unchecked serialization."""
        self.calls.append("serialization")
        raise AssertionError("hostile serializer invoked")


class ClaimUseBoundsTests(unittest.TestCase):
    """Bound complete requests before protected operations, without introducing test dependencies."""

    def setUp(self):
        """Create a real independent store in an outside-source disposable directory."""
        temporary = TemporaryDirectory(dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)/"store"
        self.store = RecordStore.create(self.root, schema_version=4)
        self.addCleanup(self.store.close)
        populate(self.store)

    def preflight_rejects(self, request, dimension):
        """Prove overflow rejects before normalization, artifact IO or any table mutation."""
        before = metadata(self.root)
        with patch.object(RecordStore, "_normalize_submission", side_effect=AssertionError("normalization reached")), \
                patch.object(self.store._artifacts, "_verify_for_commit", side_effect=AssertionError("artifact IO reached")):
            with self.assertRaisesRegex(ClaimUseLimitError, dimension):
                self.store.submit(request)
        self.assertEqual(metadata(self.root), before)

    def test_complete_request_bytes_before_normalization(self):
        """Independent sub-megabyte records cannot bypass the complete 8 MiB request ceiling."""
        value = replace(review(), assessment=replace(review().assessment, rationale="x"*950000))
        records = [assessment_envelope(f"large-{i}", 1, value, PROVENANCE) for i in range(9)]
        self.preflight_rejects(batch("request-overflow", records), "request_bytes")

    def test_record_bytes_before_normalization(self):
        """A single oversized reconstructed record fails before another complete serialization."""
        value = replace(review(), assessment=replace(review().assessment, rationale="x"*(1024*1024)))
        self.preflight_rejects(batch("record-overflow", [assessment_envelope("large", 1, value, PROVENANCE)]), "record_bytes")

    def test_artifact_count_and_bytes_before_object_io(self):
        """Declared artifact bounds precede missing-byte errors and direct artifact verification."""
        for label, artifacts in (("artifacts", [ArtifactReference(f"{i:064x}", 0) for i in range(257)]),
                                 ("artifact_bytes", [ArtifactReference("f"*64, 64*1024*1024+1)])):
            value = replace(review(), artifacts=artifacts)
            self.preflight_rejects(batch(label, [assessment_envelope(label, 1, value, PROVENANCE)]), label)

    def test_occurrences_before_cache_and_record_count_before_planning(self):
        """Repeated targets and many small proposed members consume independent occurrence/count limits."""
        repeated = [ref("candidate", "descriptive", "claim")]*4096
        records = [assessment_envelope("changed", 1, review(), PROVENANCE)]
        records.extend(RecordEnvelope(f"links-{i}", 1, "event", {}, PROVENANCE, repeated) for i in range(2))
        self.preflight_rejects(batch("references", records), "references")
        records = [assessment_envelope("changed", 1, review(), PROVENANCE)]
        records.extend(RecordEnvelope(f"small-{i}", 1, "event", {}, PROVENANCE) for i in range(1024))
        self.preflight_rejects(batch("records", records), "records")

    def test_transition_ceiling_equality_and_overflow_are_atomic(self):
        """Exactly 128 affected currents update; a required 129th rejects every ledger effect."""
        value = binding("unrelated", (), (), ())
        # Separate registration batches keep their repeated complete baseline
        # inspections within aggregate work limits; the assertion still affects
        # exactly 128 current uses in one indivisible propagation transaction.
        for start in range(0, 127, 16):
            self.store.submit_typed(batch(f"many-{start}", [use_envelope(f"u-{i}", 1, value, PROVENANCE)
                                   for i in range(start, min(start+16, 127))]))
        assessment = replace(review(candidate="unrelated"), route_assessments=[])
        self.store.submit_typed(batch("exact", [assessment_envelope("large-review", 1, assessment, PROVENANCE)]))
        for identity in ("unrelated-use", "u-0", "u-126"):
            self.assertEqual(self.store.inspect_claim_use(identity, limits=LIMITS).to_dict()["generation"], 2)
        self.store.submit_typed(batch("extra", [use_envelope("extra", 1, value, PROVENANCE)]))
        before = metadata(self.root)
        with self.assertRaisesRegex(ClaimUseLimitError, "transitions"):
            self.store.submit(batch("overflow", [assessment_envelope("large-review", 2, assessment, PROVENANCE)]))
        self.assertEqual(metadata(self.root), before)
        self.assertEqual(self.store.get_submission("overflow"), None)
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.inspect_claim_use("u-0", limits=LIMITS).to_dict()["generation"], 2)

    def test_retained_shells_reject_without_dispatch_on_all_preparation_paths(self):
        """Exact shell guards precede hostile containers/scalars for generic, typed and mixed writes."""
        from research_pipeline.domain import DomainValidationError
        from research_pipeline import claim_use_store
        from research_pipeline.tool_assessment import ToolAssessmentValidationError
        from tests.tool_assessment_store_fixtures import assessment

        before = metadata(self.root)
        for mixed in (False, True):
            for operation in (self.store.submit, self.store.submit_typed):
                for field in ("records", "kind", "_content_json", "provenance", "record_references", "reference_member",
                              "reference_scalar", "artifact_references", "artifact_member", "creator_scalar",
                              "submission_provenance", "_expected_heads_json"):
                    with self.subTest(mixed=mixed, operation=operation.__name__, field=field):
                        records = [assessment_envelope("review-a", 2, review(), PROVENANCE)]
                        if mixed:
                            records.append(assessment())
                        request = batch("hostile", records)
                        record = request.records[0]
                        trap = HostileRetainedValue()
                        if field == "records":
                            object.__setattr__(request, field, trap)
                        elif field in ("kind", "_content_json"):
                            object.__setattr__(record, field, trap)
                        elif field == "submission_provenance":
                            object.__setattr__(request, "provenance", trap)
                        elif field == "_expected_heads_json":
                            object.__setattr__(request, field, trap)
                        elif field == "reference_member":
                            object.__setattr__(record, "record_references", (trap,))
                        elif field == "reference_scalar":
                            object.__setattr__(record.record_references[0], "relationship", trap)
                        elif field == "artifact_member":
                            object.__setattr__(record, "artifact_references", (trap,))
                        elif field == "creator_scalar":
                            object.__setattr__(record.provenance, "_details_json", trap)
                        else:
                            object.__setattr__(record, field, trap)
                        expected = (ToolAssessmentValidationError if mixed and field not in ("records", "kind", "_content_json")
                                    else DomainValidationError)
                        with self.assertRaises(expected):
                            operation(request)
                        self.assertEqual(trap.calls, [])
                        self.assertEqual(metadata(self.root), before)
        # Remaining private selectors cannot accidentally reintroduce the raw scan.
        request = batch("hostile", [assessment_envelope("review-a", 2, review(), PROVENANCE)])
        trap = HostileRetainedValue()
        object.__setattr__(request, "records", trap)
        for operation in (claim_use_store.relevant_request, self.store._normalize_submission):
            with self.assertRaises(DomainValidationError):
                operation(request)
        with self.store._transaction() as connection, self.assertRaises(DomainValidationError):
            claim_use_store.prepare(self.store, connection, request)
        self.assertEqual(trap.calls, [])
        self.assertEqual(metadata(self.root), before)

    def test_freshness_detachment_ignores_instance_serializers(self):
        """Relevant generic and typed requests use checked values despite instance method overrides."""
        from tests.test_tool_assessment_persistence_bounds import Hostile
        for revision, operation in ((2, self.store.submit), (3, self.store.submit_typed)):
            request = batch(f"safe-{revision}", [assessment_envelope("review-a", revision, review(), PROVENANCE)])
            for instance in (request, request.provenance, request.records[0], request.records[0].provenance,
                             *request.records[0].record_references):
                object.__setattr__(instance, "to_dict", Hostile().to_dict)
            receipt = operation(request)
            self.assertEqual(self.store.get_submission(request.submission_id), receipt)
            self.assertEqual(self.store.head("review-a"), revision)

    def test_reverse_scans_use_bounded_index_order_before_payload(self):
        """Production temporal ranges bound both passes independently of later lifetime history.

        Copies use the production schema with synthetic isolated metadata, leaving
        foreign keys disabled only in these navigation/instruction fixtures. The
        progress handler belongs to tests, never to production admission.
        """
        import sqlite3
        from contextlib import closing
        from research_pipeline import claim_use_store as freshness

        queries = []
        original = freshness.Reader.rows

        def capture(reader, sql, args=(), dimension="index_rows"):
            """Capture complete production ranges, including explicit historical predicates."""
            queries.append((reader.cutoff, sql, args, dimension))
            yield from original(reader, sql, args, dimension)

        request = batch("scan-probes", [assessment_envelope("review-a", 2, review(), PROVENANCE)])
        with patch.object(freshness.Reader, "rows", capture), self.store._transaction() as connection:
            for cutoff in (None, 50):
                freshness.prepare(self.store, connection, request, cutoff=cutoff)
                reader = freshness.Reader(self.store, connection, cutoff=cutoff)
                freshness.observed(reader, freshness._dependencies(reader, ("use", 1)))
        indexes = ("claim_use_dependency_target", "claim_use_dependency_watch", "claim_use_upstream_target",
                   "claim_use_association_target", "claim_use_revision_event")
        probes = {}
        for cutoff, sql, args, dimension in queries:
            for index in indexes:
                if "INDEXED BY " + index in sql:
                    role = next((arg for arg in args if arg in ("assessment_watch", "issue_watch")), "")
                    probes.setdefault((index, role, cutoff), (sql, args, dimension))
        self.assertEqual(set(probes), {(index, role, cutoff) for index in indexes
                         for role in (("assessment_watch", "issue_watch") if index.endswith("watch") else ("",))
                         for cutoff in (None, 50)})
        before = metadata(self.root)
        ceiling = 8
        for (index, role, cutoff), (sql, args, dimension) in probes.items():
            with self.subTest(index=index, role=role, cutoff=cutoff), closing(sqlite3.connect(":memory:")) as connection:
                self.store._connection.backup(connection)
                for table in ("claim_use_dependencies", "claim_use_upstreams", "claim_use_bindings",
                              "claim_use_association_links", "claim_use_revision_events"):
                    connection.execute("DELETE FROM " + table)
                prefix = args[:-1] if cutoff is not None else args

                def insert_candidates(events, offset=0):
                    """Insert occurrences whose event order deliberately disagrees with identity/revision order."""
                    rows = []
                    for i, event in enumerate(events, offset):
                        identity = f"scan-{30000-i:06}"
                        if index == "claim_use_upstream_target":
                            rows.append((identity, 1, 0, 0, *prefix, event))
                        elif index in ("claim_use_dependency_target", "claim_use_dependency_watch"):
                            target = prefix if index.endswith("target") else (prefix[0], 1, prefix[1])
                            rows.append((identity, 1, 0, *target, role or "candidate", "scope", 1, 0, 0, event))
                        elif index == "claim_use_association_target":
                            connection.execute("INSERT INTO identities VALUES (?,'decision',1)", (identity,))
                            rows.append((identity, 1, 0, event, "affected_record", *prefix))
                        else:
                            rows.append((prefix[0], 30000-i, event))
                    table, width = {
                        "claim_use_upstream_target": ("claim_use_upstreams", 7),
                        "claim_use_dependency_target": ("claim_use_dependencies", 12),
                        "claim_use_dependency_watch": ("claim_use_dependencies", 12),
                        "claim_use_association_target": ("claim_use_association_links", 7),
                        "claim_use_revision_event": ("claim_use_revision_events", 3),
                    }[index]
                    connection.executemany("INSERT INTO " + table + " VALUES (" + ",".join("?" for _ in range(width)) + ")", rows)

                statements = []

                class TracedConnection:
                    """Observe both actual reader statements without changing execution."""

                    def execute(self, statement, parameters=()):
                        """Retain query and parameters for independent plan inspection."""
                        statements.append((statement, parameters))
                        return connection.execute(statement, parameters)

                def traverse(count, exhausts=False):
                    """Measure instruction work with an allowance independent of population size."""
                    ticks = 0

                    def progress():
                        """Interrupt an unbounded query and retain deterministic instruction evidence."""
                        nonlocal ticks
                        ticks += 100
                        return int(ticks > 22500)

                    reader = freshness.Reader(self.store, TracedConnection(), cutoff=cutoff)
                    reader.caps[dimension] = ceiling
                    start = len(statements)
                    connection.set_progress_handler(progress, 100)
                    try:
                        if exhausts:
                            with self.assertRaisesRegex(ClaimUseLimitError, dimension):
                                list(reader.rows(sql, args, dimension))
                        else:
                            self.assertEqual(len(list(reader.rows(sql, args, dimension))), count)
                    finally:
                        connection.set_progress_handler(None, 0)
                    self.assertEqual(reader.counts[dimension], count)
                    self.assertEqual(len(statements)-start, 1 if exhausts else 2,
                                     "sentinel exhaustion must precede payload fetching")
                    self.assertLessEqual(ticks, 22500)

                if cutoff is not None:
                    # Equality at the current event is excluded as strictly as later
                    # events; only the proposed overlay may supply current records.
                    insert_candidates([cutoff, *range(100, 20100)], offset=100)
                    traverse(0)
                insert_candidates(range(1, 9))
                traverse(8)
                if cutoff is None:
                    insert_candidates(range(100, 20100), offset=100)
                insert_candidates([9], offset=9)
                traverse(9, exhausts=True)
                for statement, parameters in statements:
                    plan = " ".join(row[-1] for row in connection.execute("EXPLAIN QUERY PLAN " + statement, parameters))
                    self.assertIn(index, plan)
                    self.assertNotIn("TEMP B-TREE FOR ORDER BY", plan)
                    if cutoff is not None:
                        event_column = "registration_event" if index in indexes[:3] else "event_id"
                        self.assertIn(event_column + "<?", plan, "cutoff must constrain the driving index search")
        self.assertEqual(metadata(self.root), before)

    def test_historical_head_and_generation_seek_visible_predecessor(self):
        """Many later revisions/transitions cannot turn predecessor point seeks into history scans."""
        import sqlite3
        from contextlib import closing
        from research_pipeline import claim_use_store as freshness

        with closing(sqlite3.connect(":memory:")) as connection:
            self.store._connection.backup(connection)
            connection.execute("DELETE FROM claim_use_revision_events")
            connection.execute("DELETE FROM claim_use_generations")
            # Revision/generation order differs from event order in this navigation
            # fixture, proving ORDER BY uses the temporal index rather than names.
            connection.executemany("INSERT INTO claim_use_revision_events VALUES ('probe',?,?)",
                                   [(30000-i, i) for i in range(1, 20010)])
            connection.executemany("INSERT INTO claim_use_generations VALUES ('probe',?,1,?,?,'requires_reassessment','[]')",
                                   [(30000-i, f"sid-{i}", i) for i in range(1, 20010)])
            statements = []
            connection.set_trace_callback(statements.append)
            ticks = 0

            def progress():
                """Count only actual SQL instructions within the two predecessor lookups."""
                nonlocal ticks
                ticks += 100
                return int(ticks > 22500)

            connection.set_progress_handler(progress, 100)
            try:
                reader = freshness.Reader(self.store, connection, cutoff=9)
                self.assertEqual(reader.head("probe"), 29992)
                self.assertEqual(reader.current("probe"), (1, 29992, 8))
            finally:
                connection.set_progress_handler(None, 0)
                connection.set_trace_callback(None)
            self.assertLessEqual(ticks, 22500)
            self.assertEqual(len(statements), 2)
            for sql, index in zip(statements, ("claim_use_revision_event", "claim_use_generation_use_event")):
                plan = " ".join(row[-1] for row in connection.execute("EXPLAIN QUERY PLAN " + sql))
                self.assertIn(index, plan)
                self.assertIn("event_id<?", plan)
                self.assertNotIn("TEMP B-TREE", plan)

    def chain(self, size, prefix):
        """Build three locally valid acyclic bindings, ordering the forward-referencing root first."""
        values = (binding("downstream", ("route-d",), ("review-d",), ("candidate",), prefix+"b"),
                  binding(routes=("route-a",), assessments=("review-a",), premises=("premise-a",), upstream=prefix+"c"),
                  binding("premise-a", (), (), ()))
        return [use_envelope(prefix+letter, 1, replace(value, limitations=[letter+"x"*size]), PROVENANCE)
                for letter, value in zip("abc", values)]

    def test_complete_baseline_rejects_large_chain_atomically(self):
        """Three 850,000-character limitations cannot fit the complete public view; mixed writes roll back."""
        for typed in (False, True):
            for stored_leaf in (False, True):
                prefix = f"large-{int(typed)}-{int(stored_leaf)}-"
                records = self.chain(850000, prefix)
                operation = self.store.submit_typed if typed else self.store.submit
                if stored_leaf:
                    operation(batch(prefix+"leaf", [records.pop()]))
                    view = self.store.inspect_claim_use(prefix+"c", limits=LIMITS).to_dict()
                    self.assertIn("c"+"x"*850000, view["limitations"])
                records.append(assessment_envelope("review-b", 2, review(route="route-b"), PROVENANCE))
                before = metadata(self.root)
                with self.subTest(typed=typed, stored_leaf=stored_leaf), \
                        patch.object(RecordStore, "_insert_submission", side_effect=AssertionError("insertion reached")), \
                        self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes|result_bytes"):
                    operation(batch(prefix+"all", records))
                self.assertEqual(metadata(self.root), before)
                self.assertIsNone(self.store.head(prefix+"a"))
                self.assertIsNone(self.store.get_submission(prefix+"all"))

    def test_complete_small_baseline_survives_reopen_and_independent_read_bounds(self):
        """Admission and standalone inspection include exact pins, all limitations, observations and causes."""
        from research_pipeline import claim_use_store as freshness
        records = self.chain(10000, "small-")
        changed = assessment_envelope("review-a", 2, replace(review(), reviewer="Prospective reviewer"), PROVENANCE)
        baseline_views = {}
        baseline_accounts = {}
        original_inspection = freshness._inspection

        def retain_baseline(reader, identity, limits):
            """Retain the prospective output to compare against immediate persisted inspection."""
            result = original_inspection(reader, identity, limits)
            baseline_views[identity] = result.to_dict()
            baseline_accounts[identity] = dict(reader.counts)
            return result

        with patch.object(freshness, "_inspection", retain_baseline):
            self.store.submit(batch("small-chain", [*records, changed]))
        before = metadata(self.root)
        persisted_accounts = {}

        def retain_persisted(reader, identity, limits):
            """Measure the immediately persisted operation without sharing any admission cache."""
            result = original_inspection(reader, identity, limits)
            persisted_accounts.update(reader.counts)
            return result

        with patch.object(freshness, "_inspection", retain_persisted):
            view = self.store.inspect_claim_use("small-a", limits=LIMITS)
        for dimension in ("metadata_bytes", "assertion_revisions", "index_rows"):
            self.assertGreaterEqual(baseline_accounts["small-a"][dimension], persisted_accounts[dimension])
        document = view.to_dict()
        prospective = baseline_views["small-a"]
        prospective["mechanical_freshness"]["last_transition"]["event_id"] = document["mechanical_freshness"]["last_transition"]["event_id"]
        self.assertEqual(prospective, document)
        self.assertEqual({b["binding"]["record_id"] for b in document["upstream_bindings"]}, {"small-b", "small-c"})
        for letter in "abc":
            self.assertIn(letter+"x"*10000, document["limitations"])
        self.assertTrue(any(a["pin"]["record_id"] == "review-a" and a["pin"]["revision"] == 2
                            and a["content"]["reviewer"] == "Prospective reviewer"
                            for a in document["observed_assertions"]))
        self.assertEqual({c["type"] for c in document["mechanical_freshness"]["reasons"]},
                         {"binding_registered", "upstream_affected", "assertion_changed"})
        self.assertFalse(document["eligible"])
        with self.assertRaisesRegex(ClaimUseLimitError, "result_bytes"):
            self.store.inspect_claim_use("small-a", limits=replace(LIMITS, max_result_bytes=len(view._json)-1))
        with self.assertRaisesRegex(ClaimUseLimitError, "metadata_bytes"):
            self.store.inspect_claim_use("small-a", limits=replace(LIMITS, max_metadata_bytes=10000))
        # Each prospective root has its own full account; aggregate work must also
        # retain those repeated preparations rather than resetting the write reader.
        prepared = []
        original = freshness._inspection

        def capture(reader, identity, limits):
            """Witness independent per-root counters and the retained aggregate write account."""
            result = original(reader, identity, limits)
            prepared.append((reader, dict(reader.counts)))
            return result

        with self.store._transaction() as connection, patch.object(freshness, "_inspection", capture):
            fresh = self.chain(100, "account-")
            plan = freshness.prepare(self.store, connection, batch("accounted", fresh))
        self.assertEqual(len({id(reader) for reader, _ in prepared}), 3)
        self.assertGreaterEqual(plan.reader.counts["metadata_bytes"], sum(c["metadata_bytes"] for _, c in prepared))
        self.assertEqual(metadata(self.root), before)
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(reopened.inspect_claim_use("small-a", limits=LIMITS), view)

    def test_reverse_observation_and_assertion_history_keep_index_order(self):
        """Actual scalar/payload discovery probes order by their index suffix, including event cutoffs."""
        from research_pipeline import claim_use_store as freshness
        statements = []
        connection = self.store._connection
        connection.set_trace_callback(statements.append)
        try:
            self.store.inspect_claim_use("downstream-use", limits=LIMITS)
            with self.store._transaction() as owned:
                reader = freshness.Reader(self.store, owned, cutoff=100)
                deps = freshness._dependencies(reader, ("use", 1))
                freshness.observed(reader, deps)
        finally:
            connection.set_trace_callback(None)
        reverse = {sql for sql in statements if "FROM claim_use_association_links l INDEXED BY claim_use_association_target" in sql}
        history = {sql for sql in statements if "FROM claim_use_revision_events" in sql
                   and "ORDER BY event_id,revision" in sql}
        self.assertTrue(reverse)
        self.assertTrue(history)
        for probes in (reverse, history):
            self.assertTrue(any("typeof(" in sql for sql in probes), "scalar preflight must be covered")
            self.assertTrue(any("typeof(" not in sql for sql in probes), "payload fetch must be covered")
            self.assertTrue(any("event_id<100" in sql for sql in probes), "historical cutoff must be covered")
            for sql in probes:
                plan = " ".join(row[-1] for row in connection.execute("EXPLAIN QUERY PLAN " + sql))
                self.assertNotIn("TEMP B-TREE FOR ORDER BY", plan)
                if probes is reverse:
                    self.assertIn("claim_use_association_target", plan)

    def test_repeated_upstream_occurrences_charge_before_cause_deduplication(self):
        """Two alternative edges to one upstream consume two work units but retain one downstream cause."""
        from research_pipeline import claim_use_store as freshness
        from research_pipeline.scientific import encode_envelope
        from tests.claim_use_fixtures import issue

        root = self.root.parent/"repeated-edges"
        with RecordStore.create(root, schema_version=4) as store:
            populate(store, uses=False)
            route = store.get_typed_revision("route-a", 1)[1]
            store.submit_typed(batch("repeat-definitions", [encode_envelope("route-copy", 1, route, PROVENANCE),
                assessment_envelope("review-copy", 1, review(route="route-copy"), PROVENANCE)]))
            leaf = binding("premise-a", (), (), ())
            alternatives = binding(routes=("route-a", "route-copy"), assessments=("review-a", "review-copy"),
                                   premises=("premise-a", "premise-a"), upstream="repeat-leaf")
            store.submit_typed(batch("repeat-register", [use_envelope("repeat-root", 1, alternatives, PROVENANCE),
                                                         use_envelope("repeat-leaf", 1, leaf, PROVENANCE)]))
            changed = batch("repeat-change", [assessment_envelope("repeat-issue", 1, issue("premise-a", "claim"), PROVENANCE)])
            before = metadata(root)
            # Three exact dependency occurrences plus two upstream occurrences
            # must be charged, although the final upstream reason is coalesced.
            with patch.object(freshness, "WRITE_LIMITS", {**freshness.WRITE_LIMITS, "causes": 4}), \
                    self.assertRaisesRegex(ClaimUseLimitError, "causes"):
                store.submit(changed)
            self.assertEqual(metadata(root), before)
            with patch.object(freshness, "WRITE_LIMITS", {**freshness.WRITE_LIMITS, "causes": 5}):
                store.submit(changed)
            document = store.inspect_claim_use("repeat-root", limits=LIMITS).to_dict()
            reasons = document["mechanical_freshness"]["reasons"]
            self.assertEqual(document["generation"], 2)
            self.assertEqual(len(reasons), 3)
            self.assertEqual(sum(reason["type"] == "upstream_affected" for reason in reasons), 1)
