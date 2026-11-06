"""Setup-only synthetic saved Source requests and candidate-first subprocess observations."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from research_pipeline.domain import CreationProvenance, RecordReference, Submission
from research_pipeline.source import SourceDeclaration, encode_envelope
from research_pipeline.source_capture import dumps_prepared_submission
from research_pipeline.store import RecordStore
from research_pipeline.work_product import encode_envelope as report_envelope
from tests.test_source import source, uninspected, known
from tests.test_assessment_store import declarations, mixed_graph
from tests.test_store import record, request
from tests.test_vault import child_environment
from tests.test_work_product import manifest

CREATOR = CreationProvenance("source-cli-creator", "2026-11-06T10:00:00.000000Z",
    {"literal": "α 𝒜\n", "signed": -2, "float": 0.25, "boolean": True})
SUBMITTER = CreationProvenance("source-cli-submitter", "2026-11-06T10:01:00.000000Z",
    {"purpose": "synthetic", "repeated": ["α 𝒜", "α 𝒜"]})


def canonical(value):
    """Encode an independent stdlib ASCII oracle, preserving ordered repeated occurrences."""
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


class SourceCliCase(unittest.TestCase):
    """Supply private stores and rich Source declarations without inheriting test-bearing suites."""

    def setUp(self):
        """Create separate report/capture histories and shared-digest inventories with inert locators."""
        temporary = TemporaryDirectory(prefix="source-cli-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.parent.chmod(0o700)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root, schema_version=7)
        self.addCleanup(self.store.close)
        self.config, self.proposal = self.parent / "config.json", self.parent / "proposal α 𝒜.json"
        self.config_value = dict(format="research_pipeline.cli_config", version=1,
                                 store=str(self.root), protected_roots=[])
        self.save(self.config, self.config_value)
        self.artifacts = tuple(self.store.put_artifact(data) for data in
                               (b"synthetic original\n", b"synthetic license\n", b"synthetic derived\n"))
        self.store.submit(request("shallow-checks", [*declarations(), record("related", kind="source")]))
        self.store.submit_typed(request("reported-checks", mixed_graph(self.artifacts[1])))
        for revision in (1, 2, 3):
            report = replace(manifest(self.artifacts[2]), product_kind="reading_report",
                supersedes=None if revision == 1 else RecordReference("report", revision - 1, "supersedes", "work_product_manifest"))
            self.store.submit_typed(Submission("report-" + str(revision), SUBMITTER,
                [report_envelope("report", revision, report, CREATOR)], {"report": revision - 1}))
        self.store.submit_typed(Submission("capture-prior", SUBMITTER,
            [encode_envelope("capture", 1, uninspected(), CREATOR)], {"capture": 0}))
        value = source(self.artifacts)
        self.value = replace(value, upstream_version=known("edition 17 β"),
            restrictions=replace(value.restrictions,
                external_processing=SourceDeclaration("prohibited", "Supplied synthetic restriction; no operating grant")),
            reading=replace(value.reading, report=RecordReference("report", 3, "reading_report", "work_product_manifest")),
            supersedes=RecordReference("capture", 1, "supersedes", "source"))
        self.saved = Submission("saved-source-original", SUBMITTER,
            [encode_envelope("capture", 2, self.value, CREATOR)], {"capture": 1})
        self.write_proposal()

    def save(self, path, value):
        """Save one explicit UTF-8 control with the required owned private leaf mode."""
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        path.chmod(0o600)

    def write_proposal(self, submission=None):
        """Save a genuine pure-codec wrapper while keeping whitespace and non-ASCII bytes authored."""
        saved = self.saved if submission is None else submission
        self.wrapper = json.loads(dumps_prepared_submission(saved))
        self.save(self.proposal, self.wrapper)

    def args(self, command="inspect-source-proposal", **options):
        """Build exact Source argv with explicit controls and independently replaceable allowances."""
        values = dict(config=self.config, proposal=self.proposal)
        values.update(options)
        return [command, *(part for key, value in values.items()
                          for part in ("--" + key.replace("_", "-"), str(value)))]

    def invoke(self, argv=None, *, expected=0, prelude="", timeout=45):
        """Execute candidate CLI code with optional deterministic child-only fault seams."""
        argv = self.args() if argv is None else argv
        command = [sys.executable, "-B", "-m", "research_pipeline", *argv]
        if prelude:
            program = prelude + "\nimport runpy, sys\nsys.argv = ['research_pipeline', *" + repr(argv) + "]\nrunpy.run_module('research_pipeline', run_name='__main__')\n"
            command = [sys.executable, "-B", "-c", program]
        result = subprocess.run(command, cwd=self.parent, env=child_environment(),
                                capture_output=True, timeout=timeout)
        self.assertEqual(result.returncode, expected, result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace"))
        if expected == 0:
            self.assertEqual(result.stderr, b"")
        return result

    def result(self, argv=None, **kwargs):
        """Return the complete domain document only after successful subprocess acknowledgement."""
        return json.loads(self.invoke(argv, **kwargs).stdout)["result"]

    def failure(self, status, *, argv=None, code=None, prelude=""):
        """Require a bounded Source-only diagnostic, with no partial success document."""
        result = self.invoke(argv, expected=status, prelude=prelude)
        self.assertEqual(result.stdout, b"")
        diagnostic = json.loads(result.stderr)
        self.assertEqual(set(diagnostic), {"format", "version", "command", "code", "message", "context"})
        self.assertEqual(set(diagnostic["context"]), {"config", "proposal", "record_id", "revision", "submission_id",
            "proposal_sha256", "submission_fingerprint", "next_action"})
        self.assertLessEqual(len(result.stderr), 65536)
        if code is not None:
            self.assertEqual(diagnostic["code"], code)
        return diagnostic
