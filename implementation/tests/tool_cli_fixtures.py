"""Private real-store Tool CLI controls and candidate subprocess helpers; no Tool execution."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from research_pipeline.domain import CreationProvenance, Submission
from tests.test_vault import child_environment
from tests.tool_assessment_store_fixtures import AssessmentCase, assessment, document
from tests.tool_registration_fixtures import declaration, tool

CREATOR = CreationProvenance("cli-creator", "2026-11-05T09:00:00.000000Z",
    {"integer": -2, "boolean": True, "float": 0.25, "nested": {"literal": "α"}})
SUBMITTER = CreationProvenance("cli-submitter", "2026-11-05T09:01:00.000000Z", {"saved": True})


def canonical(value):
    """Return an independent stdlib wire oracle, including ASCII expansion and occurrence order."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


class ToolCliCase(AssessmentCase):
    """Provide setup-only fixtures with independent process-local controls and actual SQLite state."""

    def setUp(self):
        """Create a real runtime and private explicit controls outside source and runtime roots."""
        super().setUp()
        self.parent.chmod(0o700)
        self.config = self.parent / "config.json"
        self.batch = self.parent / "batch.json"
        self.config_value = dict(format="research_pipeline.cli_config", version=1,
                                 store=str(self.root), protected_roots=[])
        self.save(self.config, self.config_value)
        self.release = declaration()
        doc = document(release=self.release)
        artifact = self.store.put_artifact(b"inert CLI attachment\n")
        self.attachment = artifact
        doc["environment"]["artifacts"] = {"state": "known", "value": [artifact.to_dict()], "reason": None}
        self.doc = doc
        assessed = assessment(doc)
        # All creation attribution is explicit and differs from each supplied reporter.
        raw = assessed.to_dict()
        raw["provenance"] = CREATOR.to_dict()
        from research_pipeline.domain import RecordEnvelope
        self.assessed = RecordEnvelope.from_dict(raw)
        self.released = tool(self.release, provenance=CREATOR)
        self.saved = Submission("cli-original", SUBMITTER, [self.assessed, self.released], {"assessment": 0, "tool": 0})
        self.write_batch()

    def save(self, path, value):
        """Save one authored UTF-8 control with exact required leaf mode."""
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        path.chmod(0o600)

    def write_batch(self, submission=None):
        """Save the complete request while allowing authored whitespace and object ordering."""
        self.batch_value = dict(format="research_pipeline.cli_tool_batch", version=1,
                                submission=(self.saved if submission is None else submission).to_dict())
        self.save(self.batch, self.batch_value)

    def args(self, command="submit-tool-records", **options):
        """Construct complete argv with explicit selection; tests may replace any one value."""
        values = dict(config=self.config)
        if command == "submit-tool-records":
            values["batch"] = self.batch
        else:
            values.update(kind="tool_assessment", record_id="assessment", revision=1)
        values.update(options)
        return [command, *(part for name, value in values.items()
                           for part in ("--" + name.replace("_", "-"), str(value)))]

    def invoke(self, argv=None, *, expected=0, prelude="", timeout=45):
        """Run the actual candidate CLI, optionally wrapping real operations with child-only faults."""
        argv = self.args() if argv is None else argv
        if prelude:
            program = prelude + "\nimport runpy, sys\nsys.argv = ['research_pipeline', *" + repr(argv) + "]\nrunpy.run_module('research_pipeline', run_name='__main__')\n"
            command = [sys.executable, "-B", "-c", program]
        else:
            command = [sys.executable, "-B", "-m", "research_pipeline", *argv]
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], env=child_environment(),
                                capture_output=True, timeout=timeout)
        self.assertEqual(result.returncode, expected, result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace"))
        if expected == 0:
            self.assertEqual(result.stderr, b"")
        return result

    def result(self, argv=None, **kwargs):
        """Decode a complete successful machine result from an actual CLI invocation."""
        return json.loads(self.invoke(argv, **kwargs).stdout)["result"]

    def failure(self, status, *, argv=None, code=None, prelude=""):
        """Require one closed diagnostic and no stdout for a refused or uncertain operation."""
        result = self.invoke(argv, expected=status, prelude=prelude)
        self.assertEqual(result.stdout, b"")
        diagnostic = json.loads(result.stderr)
        self.assertEqual(set(diagnostic), {"format", "version", "command", "code", "message", "context"})
        self.assertEqual(set(diagnostic["context"]), {"config", "batch", "kind", "record_id", "revision", "submission_id", "next_action"})
        self.assertLessEqual(len(result.stderr), 65536)
        if code is not None:
            self.assertEqual(diagnostic["code"], code)
        return diagnostic

    def mutate_batch(self, mutate):
        """Apply a test-local raw mutation to a detached saved control, avoiding shared mutable fixtures."""
        value = deepcopy(self.batch_value)
        mutate(value)
        self.save(self.batch, value)
