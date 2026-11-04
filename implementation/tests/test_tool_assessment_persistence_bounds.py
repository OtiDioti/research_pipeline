"""Assessment store retained-value safety and finite preallocation guard evidence."""

from copy import deepcopy
from contextlib import closing
import hashlib
import json
import sqlite3
from unittest.mock import patch

from research_pipeline.domain import ArtifactReference, CreationProvenance, DomainValidationError, RecordEnvelope, Submission
from research_pipeline import tool_assessment_store as bounded
from research_pipeline import store as store_module
from research_pipeline.snapshot import _classification, SnapshotLimitError
from research_pipeline.store import ReferenceResolutionError, StoreClosedError, StoreDatabaseError, _decode_typed_envelope
from research_pipeline.tool_assessment import ToolAssessment, ToolAssessmentLimitError, ToolAssessmentValidationError
from research_pipeline.tool_assessment_envelope import decode_envelope
from research_pipeline.scientific import NotTypedContentError
from tests.snapshot_fixtures import limits, selection, simple_project
from tests.test_store import record, request
from tests.test_typed_store import ref
from tests.tool_assessment_fixtures import creator, known, wire
from tests.tool_assessment_store_fixtures import AssessmentCase, assessment, document
from tests.tool_registration_fixtures import rows


def canonical(value):
    """Serialize valid fixture fields independently to measure the prescribed ASCII account."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def request_charges(batch, *, typed=True):
    """Calculate permanent, control and request bytes without production budget counters.

    Fixtures are valid before sentinels are installed. Raw retained fields and
    canonical enclosing forms are counted separately, including every occurrence.
    """
    envelopes = batch.to_dict()["records"]
    permanent = 0
    for item, fields in zip(batch.records, envelopes):
        raw = [item.record_id, str(item.revision), item.kind, item._content_json,
               item.provenance.actor, item.provenance.created_at, item.provenance._details_json]
        for link in item.record_references:
            raw.extend([link.record_id, str(link.revision), link.relationship])
            if link.target_kind is not None:
                raw.append(link.target_kind)
        for link in item.artifact_references:
            raw.extend([link.digest, str(link.size)])
        permanent += sum(len(text.encode("utf-8")) for text in raw) + len(canonical(fields))
        if typed:
            permanent += len(item._content_json)
    control = {"submission_id": batch.submission_id, "provenance": batch.provenance.to_dict(),
               "expected_heads": batch.expected_heads}
    request_size = len(canonical({"fingerprint_version": 1, "submission": batch.to_dict()}))
    permanent += sum(len(text.encode("utf-8")) for text in
                     (batch.submission_id, batch._expected_heads_json, batch.provenance.actor,
                      batch.provenance.created_at, batch.provenance._details_json)) + 2 * request_size
    return permanent, len(canonical(control)), request_size


class ProtectedStageReached(RuntimeError):
    """Witness a protected operation without allowing subsequent stages or metadata effects."""


class HostileInteger(int):
    """Detect numeric coercion or hashing before the exact-integer safety check."""

    def __str__(self):
        """Fail if preflight attempts decimal conversion of a nonexact integer."""
        raise AssertionError("numeric string hook invoked")

    def __hash__(self):
        """Fail if a nonexact integer reaches an identity cache."""
        raise AssertionError("numeric hash hook invoked")


class HostileMeta(type):
    """Detect accidental equality/hash dispatch while checking exact retained classes."""

    def __eq__(self, other):
        """Fail if a boundary compares a supplied class with equality."""
        raise AssertionError("metaclass equality invoked")

    def __hash__(self):
        """Fail if a boundary hashes a supplied class."""
        raise AssertionError("metaclass hash invoked")


class Hostile(metaclass=HostileMeta):
    """Reject arbitrary serialization, iteration and property dispatch visibly."""

    def __iter__(self):
        """Fail if a boundary iterates an unchecked supplied container."""
        raise AssertionError("iterator invoked")

    def to_dict(self):
        """Fail if a boundary serializes an unchecked supplied instance."""
        raise AssertionError("serializer invoked")


class AssessmentPersistenceBoundsTests(AssessmentCase):
    """Check raw limits before their protected operations and preserve exact error families."""

    def test_original_retained_content_and_nested_provenance_are_not_repaired(self):
        """Local malformed retries fail before reconciliation, even for a genuine saved original."""
        self.seed_release()
        original = request("original", [assessment()])
        self.store.submit_typed(original)
        baseline = rows(self.root)
        forged_kind = request("original", [assessment()])
        object.__setattr__(forged_kind.records[0], "kind", "source")
        with patch.object(RecordEnvelope, "to_dict", side_effect=AssertionError("protected serializer")), \
                self.assertRaises(ToolAssessmentValidationError):
            self.store.submit_typed(forged_kind)
        for field, value in (("_content_json", ' ' + original.records[0]._content_json),
                             ("record_references", ()), ("operational_status", "completed"),
                             ("provenance", Hostile()), ("kind", Hostile())):
            forged = request("original", [assessment()])
            object.__setattr__(forged.records[0], field, value)
            with self.subTest(field=field), self.assertRaises(ToolAssessmentValidationError):
                self.store.submit_typed(forged)
            self.assertEqual(rows(self.root), baseline)
        for field, value in (("created_at", "2026-10-30T12:35:00Z"), ("_details_json", '{"x":1,"x":1}'),
                             ("_details_json", '{"x":NaN}'), ("actor", Hostile())):
            forged = request("original", [assessment()])
            object.__setattr__(forged.records[0].provenance, field, value)
            with self.subTest(field=field), self.assertRaises(ToolAssessmentValidationError):
                self.store.submit_typed(forged)
            self.assertEqual(rows(self.root), baseline)

    def test_exact_shells_do_not_dispatch_hostile_hooks_or_instance_serializers(self):
        """Outer, nested and control forgeries fail without arbitrary hooks; exact overrides are ignored."""
        self.seed_release()
        for field, value in (("records", Hostile()), ("records", (Hostile(),)),
                             ("provenance", Hostile()), ("_expected_heads_json", Hostile())):
            batch = request("forged", [assessment()])
            object.__setattr__(batch, field, value)
            with self.subTest(field=field), self.assertRaises(DomainValidationError):
                self.store.submit_typed(batch)
        for field, value in (("record_references", Hostile()), ("artifact_references", (Hostile(),))):
            batch = request("forged", [assessment()])
            object.__setattr__(batch.records[0], field, value)
            with self.assertRaises(DomainValidationError):
                self.store.submit_typed(batch)
        batch = request("safe-overrides", [assessment()])
        for instance in (batch, batch.provenance, batch.records[0], batch.records[0].provenance, *batch.records[0].record_references):
            object.__setattr__(instance, "to_dict", Hostile().to_dict)
        self.store.submit_typed(batch)
        self.assertEqual(self.store.head("assessment"), 1)
        # Older mixed codecs may use generic serializers internally; the store
        # supplies bounded exact raw shells without these instance overrides.
        from tests.test_typed_store import context, envelope
        mixed = request("safe-mixed", [assessment(document("mixed-assessment")), envelope("mixed-context", context())])
        object.__setattr__(mixed.records[1], "to_dict", Hostile().to_dict)
        object.__setattr__(mixed.records[1].provenance, "to_dict", Hostile().to_dict)
        self.store.submit_typed(mixed)
        self.assertEqual(self.store.head("mixed-context"), 1)

    def test_root_projection_and_raw_byte_guards_precede_copy_or_decode(self):
        """Oversized tuples/text fail before serialization, parser or graph map construction."""
        for mode in ("roots", "links", "raw"):
            batch = request(mode, [assessment()])
            if mode == "roots":
                object.__setattr__(batch, "records", batch.records * 4097)
            elif mode == "links":
                object.__setattr__(batch.records[0], "record_references", batch.records[0].record_references * 32769)
            else:
                object.__setattr__(batch.records[0], "_content_json", "x" * 4194305)
            with patch.object(RecordEnvelope, "to_dict", side_effect=AssertionError("protected serializer")), \
                    patch("research_pipeline.store._decode_typed_envelope", side_effect=AssertionError("protected decoder")), \
                    self.assertRaises(ToolAssessmentLimitError):
                self.store.submit_typed(batch)

    def test_mixed_member_and_request_controls_are_revalidated(self):
        """Assessment safety handling also rejects forged mixed members and outer provenance/heads."""
        from tests.tool_registration_fixtures import declaration, tool
        for field, value in (("_expected_heads_json", '{"assessment":false,"tool":0}'),
                             ("_expected_heads_json", '{"assessment":0,"tool":0,"tool":0}')):
            batch = request("forged-heads", [assessment(), tool(declaration())])
            object.__setattr__(batch, field, value)
            with self.assertRaises(DomainValidationError):
                self.store.submit_typed(batch)
        batch = request("forged-mixed", [assessment(), tool(declaration())])
        object.__setattr__(batch.records[1], "provenance", Hostile())
        with self.assertRaises(DomainValidationError):
            self.store.submit_typed(batch)
        batch = request("forged-provenance", [assessment()])
        object.__setattr__(batch.provenance, "_details_json", '{"duplicate":1,"duplicate":2}')
        with self.assertRaises(DomainValidationError):
            self.store.submit_typed(batch)

    def test_prefix_history_and_distinct_identity_accounting(self):
        """Huge prefixes fail in constant work; overlapping prefixes and cached identities count once."""
        budget = bounded._Budget()
        budget.history(("a", 4095))
        budget.history(("a", 4000))
        budget.history(("b", 1))
        self.assertEqual(budget.history_revisions, 4096)
        with self.assertRaisesRegex(ToolAssessmentLimitError, "history_revisions"):
            budget.history(("a", 2**63 - 1))
        self.assertEqual(budget.history_revisions, 4096)
        for index in range(4096):
            budget.record((str(index), 1))
        budget.record(("0", 1))
        with self.assertRaisesRegex(ToolAssessmentLimitError, "metadata_records"):
            budget.record(("new", 1))

    def test_occurrence_and_scratch_accounts_do_not_follow_cache_hits(self):
        """Repeated projected slots count fully while rereads and temporary scratch behave independently."""
        budget = bounded._Budget()
        budget.links(("a", 1), 32768)
        budget.links(("a", 1), 32768)
        with self.assertRaisesRegex(ToolAssessmentLimitError, "reference_occurrences"):
            budget.links(("b", 1), 1)
        budget.reserve(67108863)
        with budget.temporary(1):
            self.assertEqual(budget.metadata_bytes, 67108864)
            with self.assertRaisesRegex(ToolAssessmentLimitError, "metadata_bytes"):
                budget.reserve(1)
        self.assertEqual(budget.metadata_bytes, 67108863)

    def test_sql_counts_and_raw_sizes_precede_link_materialization_and_parsing(self):
        """Stored count/raw-size checks refuse before fetching protected payloads."""
        self.seed_release()
        self.store.submit_typed(request("valid", [assessment()]))
        self.damage("UPDATE revisions SET content_json=? WHERE record_id='assessment'", ("x" * 4194305,))
        with patch.object(bounded, "_json", side_effect=AssertionError("protected parser")), \
                self.assertRaises(ToolAssessmentLimitError):
            self.store.get_typed_revision("assessment", 1)
        self.damage("UPDATE revisions SET content_json=? WHERE record_id='assessment'", (assessment()._content_json,))
        with patch.object(bounded, "MAX_REFERENCES", 0), \
                patch.object(bounded, "_json", side_effect=AssertionError("protected parser")), \
                self.assertRaisesRegex(ToolAssessmentLimitError, "reference_occurrences"):
            self.store.get_typed_revision("assessment", 1)

    def test_snapshot_small_limits_and_closed_handle_remain_authoritative(self):
        """Snapshot preflight retains smaller caller limits and closed stores reject before local decode."""
        self.seed_release()
        self.store.submit_typed(request("valid", [assessment()]))
        simple_project(self.store)
        with self.assertRaises(SnapshotLimitError):
            self.store.capture_snapshot(selection("assessment"), limits=limits(max_records=1))
        self.store.close()
        with self.assertRaises(StoreClosedError):
            self.store.submit_typed(request("closed", [assessment()]))

    def test_supplied_connection_reader_keeps_smaller_budgets_and_hooks(self):
        """The shared resolver preserves caller limit errors rather than replacing its budget with defaults."""
        from research_pipeline.operating_authority import AuthorityLimits, AuthorityLimitError
        from research_pipeline.operating_authority_store import _Reader
        self.seed_release()
        batch = request("reader", [assessment()])
        controls = AuthorityLimits(max_decisions=1, max_history_revisions=1, max_records=1, max_references=0,
            max_record_bytes=1, max_metadata_bytes=1, max_artifacts=0, max_file_bytes=1,
            max_total_bytes=0, max_result_bytes=1)
        with self.store._transaction() as connection:
            reader = _Reader(self.store, connection, controls)
            with self.assertRaises(AuthorityLimitError):
                self.store._check_typed_targets(connection, batch, (ToolAssessment.from_dict(document()),), authority_reader=reader)
        from dataclasses import replace
        roomy = replace(controls, max_records=10, max_references=32, max_record_bytes=4194304,
                        max_metadata_bytes=67108864, max_result_bytes=4194304)
        with self.store._transaction() as connection:
            reader = _Reader(self.store, connection, roomy)
            with self.assertRaisesRegex(AuthorityLimitError, "history"):
                self.store._check_typed_targets(connection, batch, (ToolAssessment.from_dict(document()),), authority_reader=reader)
        self.assertIsNone(self.store.get_submission("reader"))

    def test_stored_provenance_generic_scalars_and_retention_fail_closed(self):
        """Signed/bool/finite details survive reads; duplicate/noncanonical/depth-forged history does not."""
        self.seed_release()
        self.store.submit_typed(request("valid", [assessment()]))
        envelope, _ = self.store.get_typed_revision("assessment", 1)
        self.assertEqual(envelope.provenance.details, {"synthetic": True, "signed": -2, "fraction": 0.25, "nested": {"items": []}})
        for text in ('{"actor":"archivist","created_at":"2026-10-30T12:35:00.000000Z","details":{"x":1,"x":2}}',
                     '{"actor":"archivist","created_at":"2026-10-30T12:35:00Z","details":{}}',
                     '{ "actor":"archivist","created_at":"2026-10-30T12:35:00.000000Z","details":{}}'):
            self.damage("UPDATE revisions SET provenance_json=? WHERE record_id='assessment'", (text,))
            with self.assertRaises(ToolAssessmentValidationError):
                self.store.get_typed_revision("assessment", 1)

    def test_exact_public_receivers_and_classification_reject_retained_forgeries(self):
        """Exact receivers and local classifier do not invoke hostile instance/metaclass hooks."""
        from research_pipeline.store import RecordStore
        for method, arguments in ((RecordStore.submit_typed, (request("receiver", [assessment()]),)),
                                  (RecordStore.get_typed_revision, ("assessment", 1))):
            with self.assertRaises(DomainValidationError):
                method(Hostile(), *arguments)
        for field, value in (("record_references", Hostile()), ("provenance", Hostile()),
                             ("_content_json", ' ' + assessment()._content_json)):
            item = assessment()
            object.__setattr__(item, field, value)
            category = _classification(item, _decode_typed_envelope)
            self.assertEqual(category["category"], "malformed_typed")

    def test_huge_stored_history_prefix_is_reserved_before_predecessor_expansion(self):
        """Fresh constrained admission rejects an enormous mandatory prefix before reading N-1."""
        from research_pipeline.store import ReferenceResolutionError
        from tests.test_typed_store import ref
        from tests.tool_assessment_fixtures import known
        self.seed_release()
        self.store.submit(request("huge-original", [assessment(document("huge"))]))
        huge = 2**63 - 1
        self.damage("UPDATE revisions SET revision=? WHERE record_id='huge'", (huge,))
        self.damage("UPDATE record_links SET revision=? WHERE record_id='huge'", (huge,))
        self.damage("UPDATE identities SET head=? WHERE record_id='huge'", (huge,))
        doc = document()
        doc["lifecycle"]["supersedes"] = known([ref("huge", "supersedes_assessment", "tool_assessment", huge).to_dict()])
        original = bounded._Budget.read
        def read(budget, connection, key, reader=None):
            """Prohibit predecessor reads while retaining the actual selected metadata read."""
            if key == ("huge", huge - 1):
                raise AssertionError("history expanded before prefix reservation")
            return original(budget, connection, key, reader)
        before = rows(self.root)
        with patch.object(bounded._Budget, "read", read), self.assertRaises(ReferenceResolutionError) as caught:
            self.store.submit_typed(request("huge-consumer", [assessment(doc)]))
        self.assertIsInstance(caught.exception.__cause__, ToolAssessmentLimitError)
        self.assertIn("history_revisions", str(caught.exception))
        self.assertEqual(rows(self.root), before)

    def test_control_reconstruction_boundaries_precede_each_protected_operation(self):
        """Heads/provenance scratch reaches each sentinel at equality and refuses one byte below.

        Both submission routes and the existing preview boundary use real stores;
        operation failures refund scratch while retaining independently counted bytes.
        """
        batch = request("control-boundary", [assessment()], provenance=creator({"padding": "x" * 80000}))
        before = rows(self.root)
        budget_class = bounded._Budget
        for entry in (self.store.submit, self.store.submit_typed, self.store._check_prepared_typed):
            typed = entry != self.store.submit
            permanent, controls, _ = request_charges(batch, typed=typed)
            for stage in ("heads", "provenance"):
                original_json, original_provenance = bounded._json, bounded._provenance
                def parse(text, **kwargs):
                    """Witness expected-head parsing without intercepting member reconstruction."""
                    if stage == "heads" and text is batch._expected_heads_json:
                        raise ProtectedStageReached("heads")
                    return original_json(text, **kwargs)
                def detach(value):
                    """Witness only the outer submission's original retained provenance."""
                    if stage == "provenance" and value is batch.provenance:
                        raise ProtectedStageReached("provenance")
                    return original_provenance(value)
                for deficit in (0, 1):
                    budgets = []
                    def new_budget():
                        """Retain the actual budget for post-exception refund observations."""
                        result = budget_class()
                        budgets.append(result)
                        return result
                    with self.subTest(entry=entry.__name__, stage=stage, deficit=deficit), \
                            patch.object(bounded, "RESULT_BYTES", permanent + 6 * controls - deficit), \
                            patch.object(bounded, "_Budget", side_effect=new_budget), \
                            patch.object(bounded, "_json", parse), patch.object(bounded, "_provenance", detach):
                        expected = ToolAssessmentLimitError if deficit else ProtectedStageReached
                        with self.assertRaises(expected) as caught:
                            entry(batch)
                        self.assertIs(type(caught.exception), expected)
                        self.assertIn("metadata_bytes" if deficit else stage, str(caught.exception))
                        self.assertEqual(budgets[0].metadata_bytes, permanent)
                        self.assertEqual(rows(self.root), before)

    def test_complete_fingerprint_scratch_boundaries_and_exception_refunds(self):
        """Complete request serialization, canonicalization and hashing share one protected lifetime."""
        batch = request("fingerprint-boundary", [assessment()], provenance=creator({"escaped": "\u00e9\"\\" * 500}))
        before = rows(self.root)
        budget_class = bounded._Budget
        for entry in (self.store.submit, self.store.submit_typed):
            permanent, _, request_size = request_charges(batch, typed=entry != self.store.submit)
            for stage, target, name in (("serialization", Submission, "to_dict"),
                                        ("canonicalization", store_module, "_snapshot"),
                                        ("hashing", store_module.hashlib, "sha256")):
                for deficit in (0, 1):
                    budgets = []
                    def new_budget():
                        """Retain real accounting state without supplying expected values."""
                        result = budget_class()
                        budgets.append(result)
                        return result
                    with self.subTest(entry=entry.__name__, stage=stage, deficit=deficit), \
                            patch.object(bounded, "RESULT_BYTES", permanent + 6 * request_size - deficit), \
                            patch.object(bounded, "_Budget", side_effect=new_budget), \
                            patch.object(target, name, side_effect=ProtectedStageReached(stage)) as sentinel:
                        expected = ToolAssessmentLimitError if deficit else ProtectedStageReached
                        with self.assertRaises(expected) as caught:
                            entry(batch)
                        self.assertIs(type(caught.exception), expected)
                        self.assertIn("metadata_bytes" if deficit else stage, str(caught.exception))
                        self.assertEqual(sentinel.call_count, 0 if deficit else 1)
                        self.assertEqual(budgets[0].request_size, request_size)
                        self.assertEqual(budgets[0].metadata_bytes, permanent)
                        self.assertEqual(rows(self.root), before)

    def test_sufficient_scratch_commits_and_exact_retries_keep_fingerprint_format(self):
        """Both routes commit normally; exact retries still reserve before original-ID recovery."""
        self.seed_release()
        for typed in (False, True):
            batch = request("sufficient-" + str(typed), [assessment(document("owner-" + str(typed)))],
                            provenance=creator({"padding": "x" * 80000}))
            entry = self.store.submit_typed if typed else self.store.submit
            permanent, controls, request_size = request_charges(batch, typed=typed)
            # Serialization is this fixture's largest peak. Fresh target/history
            # work also demonstrates that its scratch was released pretransaction.
            with patch.object(bounded, "RESULT_BYTES", permanent + 6 * request_size):
                receipt = entry(batch)
            expected = hashlib.sha256(canonical({"fingerprint_version": 1, "submission": batch.to_dict()}).encode()).hexdigest()
            self.assertEqual(receipt.fingerprint, expected)
            before = rows(self.root)
            with patch.object(bounded, "RESULT_BYTES", permanent + 6 * request_size):
                self.assertEqual(entry(batch), receipt)
            for scratch_size in (controls, request_size):
                with patch.object(bounded, "RESULT_BYTES", permanent + 6 * scratch_size - 1), \
                        patch.object(Submission, "to_dict", side_effect=AssertionError("unreserved retry serializer")), \
                        self.assertRaisesRegex(ToolAssessmentLimitError, "metadata_bytes"):
                    entry(batch)
            self.assertEqual(rows(self.root), before)

    def test_valid_multi_root_large_submission_provenance_refuses_before_reconstruction(self):
        """The reported 45-root case cannot allocate six large controls above the unchanged ceiling."""
        self.seed_release()
        root_creator = creator({"padding": "x" * 250000})
        members = []
        for index in range(45):
            item = assessment(document("root-" + str(index)))
            members.append(RecordEnvelope(item.record_id, 1, item.kind, item.content, root_creator,
                                          item.record_references, item.artifact_references))
        batch = request("large-controls", members, provenance=creator({"padding": "x" * 4000000}))
        permanent, controls, _ = request_charges(batch)
        self.assertEqual(bounded.RESULT_BYTES, 67108864)
        self.assertLess(permanent + 6 * max(len(canonical(item.to_dict())) for item in members), bounded.RESULT_BYTES)
        self.assertGreater(permanent + 6 * controls, bounded.RESULT_BYTES)
        original = bounded._provenance
        def reconstruct(value):
            """Reject an attempted outer reconstruction while allowing real member decodes/copies."""
            if value is batch.provenance:
                raise AssertionError("large outer provenance reconstructed before reservation")
            return original(value)
        before = rows(self.root)
        with patch.object(bounded, "_provenance", reconstruct), \
                self.assertRaisesRegex(ToolAssessmentLimitError, "metadata_bytes") as caught:
            self.store.submit_typed(batch)
        self.assertIs(type(caught.exception), ToolAssessmentLimitError)
        self.assertEqual(rows(self.root), before)

    def test_retained_scalar_semantics_match_unchanged_assessment_decoder(self):
        """Bounded scalar forgeries retain exact codec error types and validation stages."""
        for defect in ("reference-revision", "root-revision", "record-id", "reference-id", "artifact-size"):
            for state_defect in (False, True):
                doc = document()
                if defect == "artifact-size":
                    doc["environment"]["artifacts"] = known([ArtifactReference("a" * 64, 1).to_dict()])
                batch = request("scalar", [assessment(doc)])
                item = batch.records[0]
                target, field, value = {
                    "reference-revision": (item.record_references[0], "revision", -1),
                    "root-revision": (item, "revision", 0),
                    "record-id": (item, "record_id", "bad!"),
                    "reference-id": (item.record_references[0], "record_id", "bad!"),
                    "artifact-size": (item.artifact_references[0] if item.artifact_references else item, "size", -1),
                }[defect]
                object.__setattr__(target, field, value)
                if state_defect:
                    object.__setattr__(item, "operational_status", "completed")
                before = rows(self.root)
                with self.subTest(defect=defect, state=state_defect), \
                        patch.object(RecordEnvelope, "to_dict", side_effect=AssertionError("serializer hook")), \
                        patch("research_pipeline.tool_assessment_envelope._parse", side_effect=AssertionError("premature content parse")), \
                        self.assertRaises(ToolAssessmentValidationError) as codec:
                    decode_envelope(item)
                self.assertIs(type(codec.exception), ToolAssessmentValidationError)
                with patch.object(RecordEnvelope, "to_dict", side_effect=AssertionError("serializer hook")), \
                        patch("research_pipeline.tool_assessment_envelope._parse", side_effect=AssertionError("premature content parse")), \
                        self.assertRaises(ToolAssessmentValidationError) as public:
                    self.store.submit_typed(batch)
                self.assertIs(type(public.exception), type(codec.exception))
                self.assertEqual(str(public.exception), str(codec.exception))
                self.assertIs(type(public.exception.__cause__), type(codec.exception.__cause__))
                self.assertEqual(str(public.exception.__cause__), str(codec.exception.__cause__))
                if state_defect:
                    self.assertIn("both states must be null", str(public.exception))
                self.assertEqual(rows(self.root), before)

    def test_complete_metadata_quota_precedes_negative_reference_revision(self):
        """Supplied creator metadata wins over bounded scalar syntax below the store enclosing guard."""
        batch = request("metadata-before-syntax", [assessment()])
        item = batch.records[0]
        object.__setattr__(item.record_references[0], "revision", -1)
        object.__setattr__(item.provenance, "_details_json", canonical({"padding": "x" * 270000}))
        before = rows(self.root)
        for operation in (lambda: decode_envelope(item), lambda: self.store.submit_typed(batch)):
            with patch.object(RecordEnvelope, "to_dict", side_effect=AssertionError("serializer hook")), \
                    self.assertRaisesRegex(ToolAssessmentLimitError, "max_metadata_chars") as caught:
                operation()
            self.assertIs(type(caught.exception), ToolAssessmentLimitError)
            self.assertEqual(rows(self.root), before)

    def test_unsafe_numeric_forgeries_are_assessment_errors_without_coercion(self):
        """Nonexact/hostile and unmeasurable integers fail before conversion or identity hashing."""
        before = rows(self.root)
        for value in (HostileInteger(1), Hostile(), True, 1.0, -(2**100000), 2**100000):
            for slot in ("root", "reference", "artifact"):
                doc = document()
                doc["environment"]["artifacts"] = known([ArtifactReference("a" * 64, 1).to_dict()])
                batch = request("numeric", [assessment(doc)])
                item = batch.records[0]
                target, field = ((item, "revision") if slot == "root" else
                                 (item.record_references[0], "revision") if slot == "reference" else
                                 (item.artifact_references[0], "size"))
                object.__setattr__(target, field, value)
                with self.subTest(kind=type(value).__name__, slot=slot), \
                        patch.object(RecordEnvelope, "to_dict", side_effect=AssertionError("serializer hook")), \
                        self.assertRaises(ToolAssessmentValidationError) as caught:
                    self.store.submit_typed(batch)
                self.assertIs(type(caught.exception), ToolAssessmentValidationError)
                self.assertEqual(rows(self.root), before)

    def test_missing_discriminator_and_outer_control_error_types_are_unchanged(self):
        """Deferred assessment syntax does not translate generic discriminator or outer control errors."""
        batch = request("discriminator", [assessment()])
        doc = batch.records[0].content
        del doc["format"]
        object.__setattr__(batch.records[0], "_content_json", canonical(doc))
        before = rows(self.root)
        with self.assertRaises(NotTypedContentError) as caught:
            self.store.submit_typed(batch)
        self.assertIs(type(caught.exception), NotTypedContentError)
        for field, value in (("submission_id", "bad!"), ("_expected_heads_json", '{"assessment":-1}')):
            batch = request("outer", [assessment()])
            object.__setattr__(batch, field, value)
            with self.assertRaises(DomainValidationError) as caught:
                self.store.submit_typed(batch)
            self.assertIs(type(caught.exception), DomainValidationError)
        self.assertEqual(rows(self.root), before)

    def historical_dependency_batch(self):
        """Store a valid generic historical owner; its fresh constrained consumer omits the dependency."""
        self.seed_release()
        old = document("old")
        dependency = deepcopy(wire()["environment"]["dependencies"]["value"][0])
        dependency["records"] = known([ref("dependency", "assessed_dependency", "source").to_dict()])
        dependency["artifacts"] = known([])
        old["environment"]["dependencies"] = known([dependency])
        self.store.submit(request("generic-history", [assessment(old), record("dependency", kind="source")]))
        fresh = document("fresh")
        fresh["lifecycle"]["supersedes"] = known([ref("old", "supersedes_assessment", "tool_assessment").to_dict()])
        batch = request("historical-consumer", [assessment(fresh)])
        self.assertNotIn("dependency", [pin.record_id for pin in batch.records[0].record_references])
        return batch

    def test_historical_shallow_failures_name_the_incoming_owner_and_chain_exact_causes(self):
        """Actual stored kind damage, aggregate exhaustion and identity limits identify old's edge."""
        batch = self.historical_dependency_batch()
        for mode, kind, attribute, ceiling, expected, message in (
                ("oversized", "x" * 4194305, "RESULT_BYTES", 67108864,
                 ToolAssessmentLimitError, "shallow kind"),
                ("malformed", sqlite3.Binary(b"source"), "RESULT_BYTES", 67108864,
                 ToolAssessmentValidationError, "invalid stored type"),
                ("aggregate", "x" * 4194304, "RESULT_BYTES", 1000000,
                 ToolAssessmentLimitError, "metadata_bytes"),
                ("identities", "source", "MAX_METADATA_RECORDS", 3,
                 ToolAssessmentLimitError, "metadata_records")):
            # Simulate damage outside the product boundary; its normal schema
            # CHECK rejects these stored kinds before persistence can see them.
            with closing(sqlite3.connect(self.root / "metadata.sqlite3")) as connection:
                connection.execute("PRAGMA ignore_check_constraints=ON")
                with connection:
                    connection.execute("UPDATE identities SET kind=? WHERE record_id='dependency'", (kind,))
            before = rows(self.root)
            with self.subTest(mode=mode), patch.object(bounded, attribute, ceiling), \
                    self.assertRaises(ReferenceResolutionError) as caught:
                self.store.submit_typed(batch)
            self.assertIs(type(caught.exception), ReferenceResolutionError)
            self.assertIs(type(caught.exception.__cause__), expected)
            for fragment in ("assessment old@1", "assessed_dependency", "dependency@1", message):
                self.assertIn(fragment, str(caught.exception))
            self.assertEqual(rows(self.root), before)

    def test_historical_shallow_supplied_reader_errors_propagate_by_identity(self):
        """The actual shared resolver leaves supplied-reader errors and assertions untouched."""
        from research_pipeline.operating_authority import AuthorityLimits, AuthorityLimitError, AuthorityIntegrityError
        from research_pipeline.operating_authority_store import _Reader
        batch = self.historical_dependency_batch()
        controls = AuthorityLimits(max_decisions=1, max_history_revisions=10, max_records=10, max_references=100,
            max_record_bytes=4194304, max_metadata_bytes=67108864, max_artifacts=0, max_file_bytes=1,
            max_total_bytes=0, max_result_bytes=4194304)
        before = rows(self.root)
        for error in (AuthorityLimitError("supplied limit"), AuthorityIntegrityError("supplied integrity"),
                      ToolAssessmentValidationError("supplied assessment error"), ValueError("supplied value"),
                      AssertionError("supplied assertion")):
            normalized, decoded, budget = self.store._prepare_typed_submission(batch)
            with self.store._transaction() as connection:
                reader = _Reader(self.store, connection, controls)
                with patch.object(reader, "shallow", side_effect=error) as shallow, \
                        patch.object(bounded._Budget, "shallow", side_effect=AssertionError("caller reader bypassed")), \
                        self.assertRaises(type(error)) as caught:
                    self.store._check_typed_targets(connection, normalized, decoded,
                                                   authority_reader=reader, assessment_budget=budget)
                self.assertIs(caught.exception, error)
                self.assertEqual(shallow.call_count, 1)
                self.assertEqual(shallow.call_args.args[0].record_id, "dependency")
            self.assertEqual(rows(self.root), before)

    def test_historical_shallow_sqlite_and_programmer_failures_keep_established_identities(self):
        """A real SQLite failure retains database translation; programmer assertions remain unchanged."""
        batch = self.historical_dependency_batch()
        original = bounded._Budget.shallow
        before = rows(self.root)
        errors = []
        assertion = AssertionError("shallow programmer invariant")
        for mode in ("sqlite", "assertion"):
            def shallow(budget, connection, key):
                """Run failing real SQL only on the historical shallow edge, after normal traversal."""
                if key != ("dependency", 1):
                    return original(budget, connection, key)
                if mode == "assertion":
                    raise assertion
                try:
                    connection.execute("SELECT missing_assessment_test_column FROM identities")
                except sqlite3.OperationalError as error:
                    errors.append(error)
                    raise
            with self.subTest(mode=mode), patch.object(bounded._Budget, "shallow", shallow), \
                    self.assertRaises(StoreDatabaseError if mode == "sqlite" else AssertionError) as caught:
                self.store.submit_typed(batch)
            if mode == "sqlite":
                self.assertIs(type(caught.exception), StoreDatabaseError)
                self.assertIs(caught.exception.__cause__, errors[-1])
                self.assertIs(type(errors[-1]), sqlite3.OperationalError)
            else:
                self.assertIs(caught.exception, assertion)
            self.assertEqual(rows(self.root), before)
