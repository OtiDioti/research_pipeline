"""Allocation-stage boundaries for complete lifecycle envelopes, batches and results."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import inspect
import unittest
from unittest.mock import patch

from research_pipeline import run_control as c, run_control_store as module
from research_pipeline import operating_authority_store as operating
from research_pipeline.store import RecordStore, SubmissionConflictError
from tests import run_control_fixtures as f, report_fixtures
from tests.test_store import record, request as submission


class ControlPreflightTests(unittest.TestCase):
    """Observe real reservations and constructors, keeping earlier allowances sufficient."""

    def setUp(self):
        """Create a disposable parent and allocate a new real store per independent attempt."""
        temporary = TemporaryDirectory(prefix='control-preflight-')
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.serial = 0

    def populated(self):
        """Return fresh signed setup inputs with no control history yet."""
        self.serial += 1
        store = RecordStore.create(self.parent / str(self.serial))
        self.addCleanup(store.close)
        return store, f.populate(store)

    def assert_stage(self, factory, owner, name, *, select=None):
        """Test S and S-1 remaining bytes at an explicitly selected allocation's reservation.

        Only the artificial test charge is released at equality; all production
        reservations remain live. Fresh stores isolate each public write attempt.
        """
        reserve, constructor = module._Reader.reserve, getattr(owner, name)
        attempts, targets = [], []

        def observe(reader, size):
            """Record production charges without changing allowance enforcement."""
            attempts.append(size)
            return reserve(reader, size)

        def construct(*args, **kwargs):
            """Locate the first actual construction after its last allocation reservation."""
            if not targets and (select is None or select(*args, **kwargs)):
                targets.append(len(attempts) - 1)
            return constructor(*args, **kwargs)

        if hasattr(constructor, 'from_dict'):
            construct.from_dict = constructor.from_dict
        call, verify = factory()
        with patch.object(module._Reader, 'reserve', observe), patch.object(owner, name, construct):
            result = call()
        verify(result)
        target = targets[0]
        for overflow in (1, 0):
            call, verify = factory()
            seen, charged, constructions = [], [], []

            def charge(reader, size):
                """Leave exactly the intended stage's budget, after its prerequisites finish."""
                index = len(seen)
                seen.append(size)
                if index == target:
                    self.assertEqual(size, attempts[target])
                    extra = reader.limits.max_metadata_bytes - reader.metadata_bytes - size + overflow
                    self.assertGreaterEqual(extra, 0)
                    reserve(reader, extra)
                    charged.append((reader, extra))
                return reserve(reader, size)

            def at_equality(*args, **kwargs):
                """Require reservation success before allocating the actual value."""
                if select is None or select(*args, **kwargs):
                    if not constructions:
                        self.assertEqual(overflow, 0)
                        reader, extra = charged[0]
                        self.assertEqual(reader.metadata_bytes, reader.limits.max_metadata_bytes)
                        reader.metadata_bytes -= extra
                    constructions.append(True)
                return constructor(*args, **kwargs)

            if hasattr(constructor, 'from_dict'):
                at_equality.from_dict = constructor.from_dict
            with self.subTest(constructor=name, overflow=overflow), \
                    patch.object(module._Reader, 'reserve', charge), patch.object(owner, name, at_equality):
                if overflow:
                    with self.assertRaises(c.RunControlLimitError):
                        call()
                    self.assertEqual(constructions, [])
                    verify(None)
                else:
                    verify(call())
                self.assertEqual(len(charged), 1)

    def fresh_call(self):
        """Return a public prepare call and a two-member atomicity assertion."""
        store, request = self.populated()

        def call():
            """Deliver a fresh lifecycle request using real external policy."""
            return f.commit(store, request)

        def verify(result):
            """Check zero or both members according to the actual construction outcome."""
            count = store._connection.execute("SELECT count(*) FROM revisions WHERE submission_id='prepare'").fetchone()[0]
            self.assertEqual(count, 0 if result is None else 2)
        return call, verify

    def test_fresh_envelope_and_submission_copy_reservations(self):
        """Full projected envelopes and copied batch wrappers reserve before construction."""
        for name in ('RecordEnvelope', 'Submission'):
            self.assert_stage(self.fresh_call, module, name)

    def test_authority_history_and_resolver_allocation_boundaries(self):
        """Fresh and historical paths reserve authority codecs, detached trees and the exact resolver seed."""
        def direct_decode(*args, **kwargs):
            """Select only the shared helper's direct codec call, excluding nested recovery codecs."""
            return inspect.currentframe().f_back.f_back.f_code.co_name == 'decode_authority'

        def resolver_seed(*args, **kwargs):
            """Select the resolver seed, never the earlier recovered authority submission."""
            return args[0] == 'authority_resolution'

        def historical_call():
            """Recover a real original result through historical authorization and dossier resolution."""
            store, request = self.populated()
            original = f.commit(store, request)

            def call():
                """Recover historical metadata with the shared control reader."""
                return store.get_run_control_operation('prepare', limits=f.LIMITS)

            def verify(result):
                """Recovery retains both existing members and returns the exact original when allowed."""
                self.assertEqual(store._connection.execute(
                    "SELECT count(*) FROM revisions WHERE submission_id='prepare'").fetchone()[0], 2)
                if result is not None:
                    self.assertEqual(result, original)
            return call, verify

        for factory in (self.fresh_call, historical_call):
            for owner, name, select in ((operating.authority, 'decode_envelope', direct_decode),
                    (operating.SignedOperatingDecision, 'to_dict', direct_decode),
                    (operating, 'Submission', resolver_seed)):
                self.assert_stage(factory, owner, name, select=select)

    def test_cached_authority_reconstruction_keeps_distinct_copies_charged(self):
        """Cached reads release scratch but repeated signed/tree and resolver copies retain new charges."""
        store, request = self.populated()
        reader = module._Reader(store, store._connection, f.LIMITS)
        key = operating.authority.pin(request.to_dict()['expected_authority']['reference'])
        envelope = reader.read(key)
        before = reader.metadata_bytes
        self.assertIs(reader.read(key), envelope)
        self.assertEqual(reader.metadata_bytes, before)
        for _ in range(2):
            signed, decision = reader.decode_authority(envelope)
            before += 2 * len(envelope._content_json)
            self.assertEqual(reader.metadata_bytes, before)
            self.assertEqual(signed.to_dict()['decision'], decision)

        seed_sizes = []
        constructor = operating.Submission
        reserve = reader.reserve
        charges = []

        def charged(size):
            """Observe retained seed and constructor scratch separately from typed target charges."""
            charges.append(size)
            return reserve(size)

        def seed(*args, **kwargs):
            """Independently measure the constructed seed against its preceding reservations."""
            result = constructor(*args, **kwargs)
            if args[0] == 'authority_resolution':
                size = len(c.canonical(result.to_dict()))
                self.assertEqual(charges[-2:], [size, size * 2])
                seed_sizes.append(size)
            return result

        project = operating.RecordReference.from_dict(decision['binding']['project'])
        for _ in range(2):
            before = reader.metadata_bytes
            with patch.object(reader, 'reserve', charged), patch.object(operating, 'Submission', seed):
                operating._resolve(reader, project, decision['scope'])
            self.assertGreaterEqual(reader.metadata_bytes - before, seed_sizes[-1])
        self.assertEqual(len(seed_sizes), 2)

    def test_populated_and_empty_output_copy_reservations(self):
        """Both inspection arrays and repeated detached validation consume independent bytes."""
        for populated in (False, True):
            def factory():
                """Build real optional history before measuring final inspection allocation."""
                store, request = self.populated()
                if populated:
                    f.commit(store, request)

                def call():
                    """Inspect a complete stream with normal independent output allowances."""
                    return store.inspect_run_control('run', limits=f.LIMITS)

                def verify(value):
                    """Check the complete pending list whenever the boundary allows allocation."""
                    if value is not None:
                        self.assertEqual(len(value.to_dict()['pending_obligations']), int(populated))
                return call, verify
            self.assert_stage(factory, c, 'RunControlInspection')

    def test_complete_envelope_and_submission_byte_limits(self):
        """Enclosing size overflow rejects before constructors although each content fragment fits."""
        store, request = self.populated()
        result = f.commit(store, request)
        transition = store.get_revision(c.control_id('run'), 1)
        value = transition.content
        envelope_size = len(c.canonical(transition.to_dict()))
        self.assertLess(len(transition._content_json), envelope_size)
        for overflow in (0, 1):
            limits = replace(f.LIMITS, metadata=replace(f.LIMITS.metadata, max_record_bytes=envelope_size - overflow))
            reader = module._Reader(store, store._connection, limits)
            constructor = module.RecordEnvelope
            with patch.object(module, 'RecordEnvelope', wraps=constructor) as observed:
                if overflow:
                    with self.assertRaisesRegex(c.RunControlLimitError, 'enclosing envelope'):
                        module._fresh_envelope(reader, value, actor=request.to_dict()['actor'])
                    observed.assert_not_called()
                else:
                    self.assertEqual(module._fresh_envelope(reader, value, actor=request.to_dict()['actor']), transition)
                    self.assertEqual(observed.call_count, 1)
        obligation = store.get_revision(c.obligation_id('prepare'), 1)
        raw = store._connection.execute("SELECT request_json FROM submissions WHERE submission_id='prepare'").fetchone()[0]
        for overflow in (0, 1):
            reader = module._Reader(store, store._connection, f.LIMITS)
            for envelope in (transition, obligation):
                size, nodes, depth = c._measure_json(envelope.to_dict(), c.RESULT_BYTES)
                reader.envelope_sizes[(envelope.record_id, envelope.revision)] = size
                reader.envelope_shapes[(envelope.record_id, envelope.revision)] = nodes, depth
            with patch.object(c, 'SUBMISSION_BYTES', len(raw) - overflow), \
                    patch.object(module, '_submission', wraps=module._submission) as construct:
                if overflow:
                    with self.assertRaisesRegex(c.RunControlLimitError, 'complete submission'):
                        module._fresh_submission(reader, transition, obligation, value)
                    construct.assert_not_called()
                else:
                    submitted, canonical, fingerprint = module._fresh_submission(reader, transition, obligation, value)
                    self.assertEqual(canonical, raw)
                    self.assertEqual(fingerprint, result.to_dict()['receipt']['fingerprint'])
                    self.assertEqual(len(submitted.records), 2)

    def test_stored_obligation_preflight_before_original_decode(self):
        """Actual SQL obligation content exceeding 256 KiB fails before decoding the saved batch."""
        store, request = self.populated()
        f.commit(store, request)
        store._connection.execute('UPDATE revisions SET content_json=? WHERE record_id=?',
            ('"' + 'x' * c.SMALL_BYTES + '"', c.obligation_id('prepare')))
        with patch.object(module, '_stored', side_effect=AssertionError('must preflight actual content')):
            with self.assertRaisesRegex(c.RunControlLimitError, 'member content'):
                store.get_run_control_operation('prepare', limits=f.LIMITS)

    def projected_request(self):
        """Build real preparation with the same exact reference in selection and two declarations."""
        store, request = self.populated()
        value = request.to_dict()
        reference = c.reference('project', 1, 'report_selection', 'project')
        value['report']['selection'] = [reference]
        value['report']['declarations']['results'] = [
            {'statement': report_fixtures.text('Pinned setup evidence.'), 'supporting_references': [reference]},
            {'statement': report_fixtures.text('Repeated setup evidence.'), 'supporting_references': [reference]}]
        return store, c.RunControlRequest(value)

    def test_fresh_envelope_nodes_depth_and_repeated_projections(self):
        """Actual transition/obligation trees match preflight shapes and reject before projection allocation."""
        store, request = self.projected_request()
        f.commit(store, request)
        actor = request.to_dict()['actor']
        for obligation, identity in ((False, c.control_id('run')), (True, c.obligation_id('prepare'))):
            envelope = store.get_revision(identity, 1)
            wire = json.loads(c.canonical(envelope.to_dict()))
            size, nodes, depth = c._measure_json(wire, c.RESULT_BYTES)
            value = wire['content']
            _, content_nodes, content_depth = c._measure_json(value, c.RESULT_BYTES)
            self.assertEqual(nodes, content_nodes + 12 + 5 * len(wire['record_references']))
            self.assertEqual(depth, max(content_depth + 1, 3))
            self.assertLess(content_nodes, nodes - 1)
            self.assertLess(content_depth, depth)
            self.assertEqual(sum(ref['relationship'] == 'report_selection'
                for ref in wire['record_references']), 1 if obligation else 3)
            for constant, boundary in (('JSON_NODES', nodes), ('JSON_DEPTH', depth)):
                for overflow in (0, 1):
                    reader = module._Reader(store, store._connection, f.LIMITS)
                    with self.subTest(obligation=obligation, constant=constant, overflow=overflow), \
                            patch.object(c, constant, boundary - overflow), \
                            patch.object(module, 'RecordEnvelope', wraps=module.RecordEnvelope) as construct, \
                            patch.object(module.RecordReference, 'from_dict', wraps=module.RecordReference.from_dict) as project:
                        if overflow:
                            with self.assertRaisesRegex(c.RunControlLimitError, 'enclosing envelope JSON'):
                                module._fresh_envelope(reader, value, actor=actor, obligation=obligation)
                            construct.assert_not_called()
                            project.assert_not_called()
                        else:
                            actual = module._fresh_envelope(reader, value, actor=actor, obligation=obligation)
                            self.assertEqual(actual, envelope)
                            self.assertEqual(reader.envelope_sizes[(identity, 1)], size)
                            self.assertEqual(reader.envelope_shapes[(identity, 1)], (nodes, depth))

    def test_fresh_saved_wrapper_nodes_and_depth_before_batch(self):
        """Two individually fitting envelopes still require the complete saved wrapper's node/depth budget."""
        store, request = self.projected_request()
        result = f.commit(store, request)
        envelopes = [store.get_revision(identity, 1) for identity in
            (c.control_id('run'), c.obligation_id('prepare'))]
        raw = store._connection.execute("SELECT request_json FROM submissions WHERE submission_id='prepare'").fetchone()[0]
        _, nodes, depth = c._measure_json(json.loads(raw), c.SUBMISSION_BYTES)
        shapes = [c._measure_json(envelope.to_dict(), c.RESULT_BYTES) for envelope in envelopes]
        self.assertEqual(nodes, sum(shape[1] for shape in shapes) + 12)
        self.assertEqual(depth, max(4, *(shape[2] + 3 for shape in shapes)))
        self.assertTrue(all(shape[1] < nodes - 1 and shape[2] < depth - 1 for shape in shapes))
        value = envelopes[0].content
        for constant, boundary in (('JSON_NODES', nodes), ('JSON_DEPTH', depth)):
            for overflow in (0, 1):
                reader = module._Reader(store, store._connection, f.LIMITS)
                for envelope, (size, member_nodes, member_depth) in zip(envelopes, shapes):
                    key = envelope.record_id, envelope.revision
                    reader.envelope_sizes[key] = size
                    reader.envelope_shapes[key] = member_nodes, member_depth
                with self.subTest(constant=constant, overflow=overflow), patch.object(c, constant, boundary - overflow), \
                        patch.object(module, '_submission', wraps=module._submission) as batch, \
                        patch.object(module, 'Submission', wraps=module.Submission) as construct:
                    if overflow:
                        with self.assertRaisesRegex(c.RunControlLimitError, 'complete submission JSON'):
                            module._fresh_submission(reader, *envelopes, value)
                        batch.assert_not_called()
                        construct.assert_not_called()
                    else:
                        submitted, canonical, fingerprint = module._fresh_submission(reader, *envelopes, value)
                        self.assertEqual(canonical, raw)
                        self.assertEqual(fingerprint, result.to_dict()['receipt']['fingerprint'])
                        self.assertEqual(len(submitted.records), 2)

    def test_saved_wrapper_node_boundary_commits_and_recovers_after_reopen(self):
        """Fresh equality remains recoverable at the same ceiling; one fewer node leaves neither member."""
        store, request = self.projected_request()
        f.commit(store, request)
        raw = store._connection.execute("SELECT request_json FROM submissions WHERE submission_id='prepare'").fetchone()[0]
        _, nodes, _ = c._measure_json(json.loads(raw), c.SUBMISSION_BYTES)
        for overflow in (0, 1):
            store, request = self.projected_request()
            root = self.parent / str(self.serial)
            with patch.object(c, 'JSON_NODES', nodes - overflow), \
                    patch.object(module, '_submission', wraps=module._submission) as batch, \
                    patch.object(store, '_insert_submission', wraps=store._insert_submission) as insert:
                if overflow:
                    with self.assertRaisesRegex(c.RunControlLimitError, 'complete submission JSON'):
                        f.commit(store, request)
                    batch.assert_not_called()
                    insert.assert_not_called()
                    self.assertIsNone(store.head(c.control_id('run')))
                    self.assertIsNone(store.head(c.obligation_id('prepare')))
                else:
                    original = f.commit(store, request)
                    self.assertEqual(insert.call_count, 1)
                    store.close()
                    with RecordStore.open(root) as reopened:
                        self.assertEqual(reopened.get_run_control_operation('prepare', limits=f.LIMITS), original)
                        self.assertEqual(f.commit(reopened, request, policy=None, evaluated_at=None), original)

    def test_actual_stored_content_equality_and_one_byte_overflow(self):
        """The role-specific SQL guard permits equality and forbids decoding one byte over."""
        store, request = self.populated()
        f.commit(store, request)
        envelope = store.get_revision(c.obligation_id('prepare'), 1)
        size = len(envelope._content_json)
        for overflow in (0, 1):
            reader = module._Reader(store, store._connection, f.LIMITS)
            with patch.object(c, 'SMALL_BYTES', size - overflow), patch.object(module, '_stored', wraps=module._stored) as decode:
                if overflow:
                    with self.assertRaisesRegex(c.RunControlLimitError, 'member content'):
                        reader.read((envelope.record_id, 1))
                    decode.assert_not_called()
                else:
                    self.assertEqual(reader.read((envelope.record_id, 1)), envelope)
                    self.assertGreater(decode.call_count, 0)

    def test_lexical_nodes_keys_escapes_and_utf8(self):
        """Value tokens, escaped quote boundaries and UTF-8 lengths are checked before json.loads."""
        values = [{'key': [None, True, -1.5, '\\"\n😀']}, {'\\"': 'é\x01'}, [1, {'a': []}]]
        for value in values:
            text = json.dumps(value, ensure_ascii=False)
            _, nodes, _ = c._measure_json(value, c.RESULT_BYTES)
            with patch.object(c, 'JSON_NODES', nodes):
                self.assertEqual(c.strict_json(text, 1000), value)
            with patch.object(c, 'JSON_NODES', nodes - 1), patch.object(c.json, 'loads', side_effect=AssertionError('node allocation')):
                with self.assertRaises(c.RunControlValidationError):
                    c.strict_json(text, 1000)
        text = '"' + '😀' * 10 + '"'
        self.assertEqual(c.strict_json(text, 122), '😀' * 10)
        with patch.object(c.json, 'loads', side_effect=AssertionError('UTF-8 allocation')):
            with self.assertRaises(c.RunControlLimitError):
                c.strict_json(text, len(text.encode('utf-8')) - 1)
        text = '[' + ','.join('null' for _ in range(c.JSON_NODES)) + ']'
        with patch.object(c.json, 'loads', side_effect=AssertionError('node allocation')):
            with self.assertRaises(c.RunControlValidationError):
                c.strict_json(text, c.RESULT_BYTES)

    def test_nested_control_token_is_an_unrelated_operation(self):
        """Descriptive generic content cannot misclassify a valid unrelated original submission."""
        store, request = self.populated()
        generic = submission('prepare', [record('description', content={'nested': {'format': c.FORMATS[0]}})])
        original = store.submit(generic)
        with self.assertRaises(SubmissionConflictError):
            f.commit(store, request)
        self.assertEqual(store.submit(generic), original)

    def test_nested_authority_results_reject_before_construction(self):
        """Control-owned authority reconstruction checks its own result ceiling at nested stages."""
        store, request = self.populated()
        # A tiny authority ceiling must reject the recovered decision result,
        # before either its constructor or the final eligibility constructor.
        limits = replace(f.LIMITS, metadata=replace(f.LIMITS.metadata, max_result_bytes=1))
        with patch.object(operating, 'DecisionCommitResult', side_effect=AssertionError('nested result allocated')):
            with self.assertRaises(c.RunControlLimitError):
                f.commit(store, request, limits=limits)
        self.assertIsNone(store.head(c.control_id('run')))

    def test_independent_record_history_and_reference_allowances(self):
        """Each complete traversal counter permits equality and rejects one fewer with other budgets ample."""
        store, request = self.populated()
        f.commit(store, request)
        readers = []
        reader_type = module._Reader

        def reader(*args, **kwargs):
            """Observe real complete traversal accounting without replacing reader behavior."""
            instance = reader_type(*args, **kwargs)
            readers.append(instance)
            return instance

        with patch.object(module, '_Reader', side_effect=reader):
            expected = store.inspect_run_control('run', limits=f.LIMITS)
        observed = readers[-1]
        counts = {'max_records': len(observed.records), 'max_history_revisions': len(observed.histories),
            'max_references': observed.references}
        for field, count in counts.items():
            self.assertGreater(count, 0)
            limits = replace(f.LIMITS, metadata=replace(f.LIMITS.metadata, **{field: count}))
            self.assertEqual(store.inspect_run_control('run', limits=limits), expected)
            with self.subTest(field=field), self.assertRaises(c.RunControlLimitError):
                store.inspect_run_control('run', limits=replace(limits, metadata=replace(limits.metadata, **{field: count - 1})))

    def test_independent_selected_artifact_allowances(self):
        """Real main-research artifacts enforce count/file/total boundaries before any verification read."""
        from research_pipeline.artifacts import ArtifactStore
        for field in ('max_artifacts', 'max_file_bytes', 'max_total_bytes'):
            self.serial += 1
            store = RecordStore.create(self.parent / str(self.serial))
            self.addCleanup(store.close)
            request = f.populate(store, main=True)
            eligible = store.inspect_operating_eligibility('synthetic', 'project', purpose='main_research',
                policy=f.authority.policy(), evaluated_at=f.authority.TIME, limits=f.authority.LIMITS).to_dict()
            artifacts = eligible['verified_artifacts']
            count = {'max_artifacts': len(artifacts), 'max_file_bytes': max(item['size'] for item in artifacts),
                'max_total_bytes': sum(item['size'] for item in artifacts)}[field]
            denied = replace(f.LIMITS, metadata=replace(f.LIMITS.metadata, **{field: count - 1}))
            with self.subTest(field=field), patch.object(ArtifactStore, 'verify', side_effect=AssertionError('must preflight artifacts')):
                with self.assertRaises(c.RunControlLimitError):
                    f.commit(store, request, limits=denied)
            self.assertIsNone(store.head(c.control_id('run')))
            accepted = replace(f.LIMITS, metadata=replace(f.LIMITS.metadata, **{field: count}))
            self.assertEqual(f.commit(store, request, limits=accepted).to_dict()['disposition'], 'prepared')

    def test_stored_enclosing_envelope_ceiling_precedes_constructor(self):
        """Stored envelope overhead has its own equality boundary after content-length preflight."""
        store, request = self.populated()
        f.commit(store, request)
        envelope = store.get_revision(c.obligation_id('prepare'), 1)
        size = len(c.canonical(envelope.to_dict()))
        self.assertLess(len(envelope._content_json), size - 1)
        constructor = operating.RecordEnvelope
        for overflow in (0, 1):
            limits = replace(f.LIMITS, metadata=replace(f.LIMITS.metadata, max_record_bytes=size - overflow))
            reader = module._Reader(store, store._connection, limits)
            with patch.object(operating, 'RecordEnvelope', wraps=constructor) as observed:
                if overflow:
                    with self.assertRaises(c.RunControlLimitError), module._errors():
                        reader.read((envelope.record_id, 1))
                    observed.assert_not_called()
                else:
                    self.assertEqual(reader.read((envelope.record_id, 1)), envelope)
                    self.assertEqual(observed.call_count, 1)
