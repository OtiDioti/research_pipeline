"""Real candidate CLI equivalence, schema versions, immutable pins and complete pages."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.claim_use import ClaimUseInspectionLimits, encode_envelope as use_envelope
from research_pipeline.domain import RecordEnvelope
from research_pipeline.store import RecordStore
from tests.claim_use_fixtures import (
    LIMITS, PROVENANCE, batch, populate, ref, review, issue, assessment_envelope,
    support_context_graph, target_context_graph,
)
from tests.test_claim_use_context import context_record
from tests.test_claim_use_store import metadata
from tests.test_vault import child_environment

COMMANDS = ("inspect-claim-use", "inspect-claim-use-history")


def canonical(value):
    """Encode expected wire bytes independently with the standard library, preserving array order."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)+"\n").encode("ascii")


class ClaimUseCliCase(unittest.TestCase):
    """Isolate private stores, controls and actual candidate subprocesses for each test."""

    def setUp(self):
        """Create schema-7 selected scopes and owned config outside source with non-ASCII runtime identity."""
        temporary = TemporaryDirectory(dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / 'runtime-α-😀'
        self.store = RecordStore.create(self.root, schema_version=7)
        self.addCleanup(self.store.close)
        self.fixture = support_context_graph(self.store)
        self.config = self.parent / 'config.json'
        self.config_value = dict(format="research_pipeline.cli_config", version=1,
                                 store=str(self.root), protected_roots=[])
        self.save(self.config_value)

    def save(self, value):
        """Write a private authored control, retaining its actual UTF-8 rather than canonical ASCII size."""
        self.config.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        self.config.chmod(0o600)

    def args(self, command=COMMANDS[0], **options):
        """Build explicit selections, allowing tests to replace individual argv tokens."""
        values = dict(config=self.config, use_id="use")
        values.update(options)
        return [command, *(part for name, value in values.items()
                          for part in ("--"+name.replace("_", "-"), str(value)))]

    def invoke(self, argv=None, *, expected=0, prelude="", timeout=45):
        """Run the actual candidate command; child-only hooks never change the parent process."""
        argv = self.args() if argv is None else argv
        if prelude:
            code = prelude + "\nimport runpy, sys\nsys.argv=['research_pipeline', *"+repr(argv)+"]\nrunpy.run_module('research_pipeline', run_name='__main__')\n"
            command = [sys.executable, "-B", "-c", code]
        else:
            command = [sys.executable, "-B", "-m", "research_pipeline", *argv]
        result = subprocess.run(command, cwd=self.parent, env=child_environment(), capture_output=True, timeout=timeout)
        self.assertEqual(result.returncode, expected, result.stdout.decode(errors="replace")+result.stderr.decode(errors="replace"))
        if expected == 0:
            self.assertEqual(result.stderr, b"")
        return result

    def failure(self, command=COMMANDS[0], *, status=5, code="invalid_input", prelude="", **options):
        """Require a bounded diagnostic with the exact read-only context and no result bytes."""
        process = self.invoke(self.args(command, **options), expected=status, prelude=prelude)
        self.assertEqual(process.stdout, b"")
        diagnostic = json.loads(process.stderr)
        self.assertEqual(set(diagnostic), {"format", "version", "command", "code", "message", "context"})
        self.assertEqual(diagnostic["format"], "research_pipeline.cli_diagnostic")
        self.assertEqual(diagnostic["version"], 1)
        self.assertEqual(diagnostic["command"], command)
        self.assertEqual(diagnostic["code"], code)
        self.assertEqual(set(diagnostic["context"]), {"config", "use_id", "after_generation", "page_limit", "next_action"})
        self.assertLessEqual(len(process.stderr), 65536)
        self.assertTrue(process.stderr.isascii())
        self.assertNotIn("inspect-receipt", diagnostic["context"]["next_action"])
        return diagnostic

    def equivalent(self, command=COMMANDS[0], *, store=None, expected=0, prelude="", **options):
        """Compare full API documents and independent canonical framing against actual subprocess bytes."""
        selected = store or self.store
        identity = options.get("use_id", "use")
        history = command == COMMANDS[1]
        limits = ClaimUseInspectionLimits(**{name: options.get(name, getattr(LIMITS, name))
                                            for name in LIMITS.__dataclass_fields__})
        domain = None if expected == 3 else (
            selected.claim_use_history(identity, after_generation=int(options.get("after_generation", 0)),
                limit=int(options.get("page_limit", 256)), limits=limits).to_dict()
            if history else selected.inspect_claim_use(identity, limits=limits).to_dict())
        result = dict(store=str(selected._artifacts._root), use_id=identity)
        if history:
            result.update(after_generation=int(options.get("after_generation", 0)), page_limit=int(options.get("page_limit", 256)))
        result["history" if history else "inspection"] = domain
        outer = dict(format="research_pipeline.cli_result", version=1, command=command,
                     status="absent" if expected else "ok", result=result)
        process = self.invoke(self.args(command, **options), expected=expected, prelude=prelude)
        self.assertEqual(process.stderr, b"")
        self.assertEqual(process.stdout, canonical(outer))
        self.assertEqual(set(json.loads(process.stdout)), {"format", "version", "command", "status", "result"})
        return domain

    def state(self):
        """Snapshot every application table and original object bytes/modes, including reservations when seeded."""
        objects = {path.name: (path.read_bytes(), path.stat().st_mode) for path in (self.root/'objects').iterdir()}
        return metadata(self.root), objects


class ClaimUseCliEquivalenceTests(ClaimUseCliCase):
    """Complete observations retain domain semantics without deriving new CLI interpretations."""

    def test_selected_public_operation_called_once_with_six_unchanged_limits(self):
        """Present and absent invocations use exactly their public API, retaining independent selected values."""
        allowances = dict(max_bindings=16, max_records=128, max_references=4096,
                          max_assertion_revisions=128, max_metadata_bytes=16777216, max_result_bytes=2097152)
        prelude = f'''
import json
from pathlib import Path
from research_pipeline.store import RecordStore

def instrument(name):
    """Observe real public calls without substituting documents or changing their work."""
    original = getattr(RecordStore, name)
    def operation(self, identity, **kwargs):
        """Record each invocation independently before delegating to the genuine snapshot operation."""
        limits = kwargs["limits"]
        with Path("calls").open("a") as stream:
            stream.write(json.dumps(dict(operation=name, use_id=identity,
                limits={{key: getattr(limits, key) for key in {tuple(allowances)!r}}},
                selections={{key: value for key, value in kwargs.items() if key != "limits"}}))+"\\n")
        return original(self, identity, **kwargs)
    setattr(RecordStore, name, operation)
instrument("inspect_claim_use")
instrument("claim_use_history")
'''
        for command in COMMANDS:
            for identity, status in (('use', 0), ('absent', 3)):
                marker = self.parent/'calls'
                if marker.exists():
                    marker.unlink()
                selections = dict(after_generation=0, page_limit=1) if command == COMMANDS[1] else {}
                self.equivalent(command, use_id=identity, expected=status, prelude=prelude, **selections, **allowances)
                calls = [json.loads(line) for line in marker.read_text().splitlines()]
                self.assertEqual(calls, [dict(operation='claim_use_history' if command == COMMANDS[1] else 'inspect_claim_use',
                    use_id=identity, limits=allowances,
                    selections=dict(after_generation=0, limit=1) if command == COMMANDS[1] else {})])

    def test_schema_versions_and_full_canonical_documents(self):
        """All four supported schemas preserve their nested inspection versions and history version one."""
        for schema, version in ((4, 1), (5, 2), (6, 3), (7, 4)):
            root = self.parent / ('schema-'+str(schema))
            with RecordStore.create(root, schema_version=schema) as store:
                if schema == 6:
                    target_context_graph(store)
                else:
                    populate(store)
                self.save({**self.config_value, "store": str(root)})
                before = metadata(root)
                self.assertEqual(self.equivalent(store=store)["version"], version)
                self.assertEqual(self.equivalent(COMMANDS[1], store=store)["version"], 1)
                self.assertEqual(metadata(root), before)

    def test_complete_context_roles_shared_occurrences_and_historical_rebinding(self):
        """Current U follows U@2 while D keeps complete old scope at U@1, including repeated occurrences."""
        original = self.equivalent()["binding"]
        self.store.submit_typed(batch("rebind", [use_envelope("use", 2, self.fixture["independent"], PROVENANCE)]))
        self.store.submit(batch("old-scope", [context_record("support-evidence", question='old α 😀 " \\'),
            context_record("support-target", question="Old bound target changed after U rebinding")]))
        current = self.equivalent()
        downstream = self.equivalent(use_id="downstream-use")
        self.assertEqual(current["binding_revision"], 2)
        self.assertEqual(downstream["upstream_bindings"][0], original)
        self.assertTrue(any(o["bound_context"]["record_id"] == "support-target" and o["superseded"]
                            for o in downstream["observed_target_contexts"]))
        self.assertTrue(any(o["source_role"] == "evidence" and o["superseded"] for o in downstream["observed_support_contexts"]))
        self.equivalent(COMMANDS[1], use_id="downstream-use", page_limit=1)
        exact = self.invoke(["inspect-record", "--config", str(self.config), "--record-id", "use", "--revision", "1"])
        self.assertEqual(json.loads(exact.stdout)["result"]["envelope"], original["envelope"])
        self.assertNotIn("generation", original)
        shared_root = self.parent/'shared'
        with RecordStore.create(shared_root, schema_version=7) as shared:
            support_context_graph(shared, shared=True)
            shared.submit(batch("shared-change", [context_record("support-shared")]))
            self.save({**self.config_value, "store": str(shared_root)})
            view = self.equivalent(store=shared)
            self.assertEqual(len(view["observed_support_contexts"]), 8)
            self.assertEqual({o["source_role"] for o in view["observed_support_contexts"]}, {"candidate_claim", "support_route", "premise", "evidence"})
            self.assertEqual(len(view["routes"][0]["premises"]), 2)
            self.assertEqual(len(view["routes"]), 2)
            self.assertFalse(view["eligible"])
            self.assertTrue(view["requires_reassessment"])
            self.assertFalse(view["authorized_disposition"]["available"])
            self.assertEqual(view["attachment_availability"], "not_checked_metadata_only")
            self.assertTrue(view["limitations"])

    def test_policy_review_withdrawal_retarget_issue_resolution_reopening_and_removal(self):
        """Every assertion and policy transition retains its complete original cause and scope fields."""
        self.store.submit(batch("policy-next", [RecordEnvelope("policy", 2, "decision", {"note": "α 😀"}, PROVENANCE)]))
        original_review = review("s-candidate", "s-route-a", "support-target")
        withdrawn = replace(original_review, assessment=replace(original_review.assessment,
                            rationale='Withdrawn "prose" α 😀', scientific_disposition="support_withdrawn"))
        retarget = review("candidate", "route-a", "scope")
        for revision, value in ((2, withdrawn), (3, retarget)):
            self.store.submit_typed(batch("review-"+str(revision), [assessment_envelope("s-review-a", revision, value, PROVENANCE)]))
            self.equivalent()
        value = issue("s-route-a")
        for revision, next_value in ((1, value), (2, replace(value, disposition="resolved")),
                                     (3, value), (4, replace(value, affected_records=[ref("unrelated", "affected_record", "claim")]))):
            self.store.submit_typed(batch("issue-"+str(revision), [assessment_envelope("issue", revision, next_value, PROVENANCE)]))
            self.equivalent()
            self.equivalent(COMMANDS[1])
        before = self.state()
        self.equivalent(use_id="downstream-use")
        self.equivalent(COMMANDS[1], use_id="downstream-use")
        self.assertEqual(self.state(), before)

    def test_complete_multiple_pages_empty_max_cursor_and_absence(self):
        """Returned cursors traverse all genuine transitions and distinguish empty registered pages from absence."""
        for revision in range(2, 7):
            self.store.submit(batch("advance-"+str(revision), [context_record("support-evidence", revision)]))
        complete = self.store.claim_use_history("use", limits=LIMITS).to_dict()["transitions"]
        for page_limit in (1, 4, 256):
            cursor, transitions = 0, []
            while True:
                page = self.equivalent(COMMANDS[1], after_generation=cursor, page_limit=page_limit)
                transitions.extend(page["transitions"])
                if page["next_cursor"] is None:
                    break
                self.assertEqual(page["next_cursor"], page["transitions"][-1]["generation"])
                cursor = page["next_cursor"]
            self.assertEqual(transitions, complete)
        self.equivalent(COMMANDS[1])
        for cursor in (6, 7, 9223372036854775807):
            page = self.equivalent(COMMANDS[1], after_generation=cursor)
            self.assertEqual(page["transitions"], [])
            self.assertIsNone(page["next_cursor"])
        self.store.submit(batch("generic", [RecordEnvelope("generic", 1, "promotion_eligibility", {}, PROVENANCE)]))
        before = self.state()
        for command in COMMANDS:
            for identity in ("missing", "generic", "0", "a"*128):
                self.equivalent(command, use_id=identity, expected=3)
        exact = self.invoke(["inspect-record", "--config", str(self.config), "--record-id", "generic", "--revision", "1"])
        self.assertEqual(json.loads(exact.stdout)["result"]["envelope"]["content"], {})
        self.assertEqual(self.state(), before)

    def test_default_and_maximum_pages_have_real_continuations_and_final_nonfull_page(self):
        """More than 256 genuine registrations exercise default/max page continuation without manufactured rows."""
        for revision in range(2, 259):
            self.store.submit_typed(batch('long-history-'+str(revision), [
                use_envelope('unrelated-use', revision, self.fixture['independent'], PROVENANCE)]))
        api_first = self.store.claim_use_history('unrelated-use', limits=LIMITS).to_dict()
        self.assertEqual(len(api_first['transitions']), 256)
        self.assertEqual(api_first['next_cursor'], 256)
        api_last = self.store.claim_use_history('unrelated-use', after_generation=256, limits=LIMITS).to_dict()
        self.assertEqual(len(api_last['transitions']), 2)
        self.assertIsNone(api_last['next_cursor'])
        expected = api_first['transitions']+api_last['transitions']
        before = self.state()
        for options in ({}, {'page_limit': 256}):
            first = self.equivalent(COMMANDS[1], use_id='unrelated-use', **options)
            last = self.equivalent(COMMANDS[1], use_id='unrelated-use', after_generation=first['next_cursor'], **options)
            self.assertEqual(first['transitions']+last['transitions'], expected)
        self.assertEqual(self.state(), before)

    def test_metadata_only_after_attachment_damage_and_deletion_in_fresh_processes(self):
        """No wrapper adds old attachment verification; original damaged-state baselines remain unchanged."""
        self.config.chmod(0o400)
        expected = {command: self.equivalent(command) for command in COMMANDS}
        path = self.root/'objects'/self.fixture["artifact"].digest
        for damage in (True, False):
            if damage:
                path.chmod(0o600)
                path.write_bytes(b'x'*self.fixture["artifact"].size)
                path.chmod(0o400)
            else:
                path.unlink()
            before = self.state()
            guard = '''
from pathlib import Path
from research_pipeline.artifacts import ArtifactStore

def forbidden(self, *args, **kwargs):
    """Refuse any historical byte verification introduced by the wrappers."""
    Path("attachment-guard").write_text("called")
    raise AssertionError("metadata-only attachment verification")
ArtifactStore.verify = forbidden
'''
            for command in COMMANDS:
                self.assertEqual(self.equivalent(command, prelude=guard), expected[command])
            self.assertFalse((self.parent/'attachment-guard').exists())
            self.assertEqual(self.state(), before)
