"""Tool qualification/ownership tests. Supplied science never runs on the host."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tests import use_checkout
use_checkout()
from research_pipeline import isolation, tools, workspace


def tool_fixture(root, origin="user"):
    root.mkdir(parents=True, exist_ok=True)
    value = {"version": 1, "name": "sum", "origin": origin, "purpose": "Sum finite values.",
             "files": ["method.py", "check.py"], "invocation": ["python3", "method.py"],
             "dependencies": ["Python standard library"],
             "checks": [{"description": "Check a known finite sum.", "argv": ["python3", "check.py"]}],
             "limitations": "Floating-point error and overflow require assessment."}
    (root / "tool.json").write_text(json.dumps(value))
    (root / "method.py").write_text("print(sum([1, 2, 3]))\n")
    (root / "check.py").write_text("assert sum([1, 2, 3]) == 6\n")
    return root / "tool.json"


def success(context, argv, cwd):
    """Explicit execution double: observations are engineering fixtures."""
    return {"argv": argv, "cwd": str(cwd), "outcome": "successful", "returncode": 0,
            "stdout": "engineering execution double", "stderr": "",
            "stdout_clipped": False, "stderr_clipped": False}


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.prior = self.root / "prior"
        self.original = tool_fixture(self.prior / "work/tools/sum")
        self.catalog = {"prior": {"path": str(self.prior), "root": str(self.prior), "available": True}}
        self.drafts = self.project / ".research_pipeline/drafts"
        self.drafts.mkdir(parents=True)
        self.control = self.project / ".research_pipeline/control"
        self.control.mkdir()
        (self.project / "work").mkdir()
        self.context = {"project": str(self.project), "workspace": "work", "drafts": str(self.drafts),
                        "excluded": ["work/tasks"], "activation": "first", "task": "primary",
                        "deadline": time.monotonic() + 10, "control": str(self.control)}
        self.assessment = "work/tools/local/ASSESSMENT.md"

    def staged(self):
        staged = tools.stage(self.context, self.catalog, "work/tools/sum/tool.json", "local", "prior")
        assessment = self.drafts / self.assessment
        assessment.parent.mkdir(parents=True, exist_ok=True)
        assessment.write_text("# Intended use\nFinite sums; elementary checks only. Overflow remains uncertain.")
        return staged["description"]

    def register(self):
        rel = self.staged()
        return rel, tools.register(self.context, rel, self.assessment, runner=success)

    def test_user_and_agent_working_copy_registration_and_reuse(self):
        before = {str(p): p.read_bytes() for p in self.prior.rglob("*") if p.is_file()}
        self.assertEqual(tools.discover(self.context, self.catalog)["tools"], [])
        candidate = tools.discover(self.context, self.catalog, candidates=True)["tools"][0]
        self.assertFalse(candidate["eligible"])
        rel, validation = self.register()
        self.assertEqual(validation["source"]["staged_from"]["root"], str(self.prior))
        self.assertEqual(validation["source"]["staged_from"]["hashes"],
                         tools.identities(self.original, tools.load_description(self.original)))
        self.assertEqual(tools.discover(self.context, {}, candidates=False)["tools"][0]["path"], rel)
        result = tools.run(self.context, rel, ["--output", "observations.json"], runner=success)
        self.assertEqual(result["argv"], ["python3", "method.py", "--output", "observations.json"])
        self.assertTrue((self.drafts / result["receipt"]).exists())
        self.assertFalse((self.project / Path(rel).with_name(tools.RECORD)).exists())
        agent = tool_fixture(self.project / "work/tools/agent", "agent")
        agent_assessment = self.drafts / "work/tools/agent/USE.md"
        agent_assessment.parent.mkdir(parents=True)
        agent_assessment.write_text("# Agent use\nCheck finite values; no universal accuracy claim.")
        tools.register(self.context, agent.relative_to(self.project), "work/tools/agent/USE.md", runner=success)
        self.assertEqual(len(tools.discover(self.context, {})["tools"]), 2)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.prior.rglob("*") if p.is_file()})

    def test_invalid_descriptions_and_missing_payloads_are_actionable_candidates(self):
        value = json.loads(self.original.read_text())
        for key, bad in (("version", True), ("version", 2), ("origin", "trusted"),
                         ("purpose", ""), ("limitations", []), ("files", []),
                         ("files", ["../escape"]), ("files", ["/etc/passwd"]),
                         ("files", [".private"]), ("files", ["missing.py"]),
                         ("files", ["method.py", "method.py"]), ("invocation", "python3 method.py"),
                         ("dependencies", "automatic"), ("checks", []),
                         ("checks", [{"description": "test", "argv": []}])):
            with self.subTest(key=key, value=bad):
                self.original.write_text(json.dumps({**value, key: bad}))
                with self.assertRaises((tools.ToolError, OSError)):
                    tools.load_description(self.original)
                result = tools.discover(self.context, self.catalog, candidates=True)
                self.assertFalse(result["tools"][0]["eligible"])
        self.original.write_text(json.dumps({**value, "dependencies": []}))
        self.assertEqual(tools.load_description(self.original)["dependencies"], [])
        (self.original.parent / "method.py").unlink()
        (self.original.parent / "method.py").symlink_to(self.original.parent / "check.py")
        with self.assertRaisesRegex(tools.ToolError, "Symlink"):
            tools.load_description(self.original)

    def test_changed_files_assessment_activation_and_pending_records_invalidate(self):
        rel, _ = self.register()
        context = {**self.context, "activation": "fresh"}
        with self.assertRaisesRegex(tools.ToolError, "Fresh activation"):
            tools.run(context, rel, [], runner=success)
        tools.register(context, rel, self.assessment, runner=success)
        tools.run(context, rel, [], runner=success)
        (self.drafts / self.assessment).write_text("# Human revised applicability")
        with self.assertRaisesRegex(tools.ToolError, "Assessment changed"):
            tools.run(context, rel, [], runner=success)
        tools.register(context, rel, self.assessment, runner=success)
        (self.project / Path(rel).with_name("method.py")).write_text("# Changed calculation")
        with self.assertRaisesRegex(tools.ToolError, "files changed"):
            tools.run(context, rel, [], runner=success)
        self.assertFalse(tools.discover(context, {}, candidates=True)["tools"][0]["eligible"])
        with self.assertRaisesRegex(tools.ToolError, "nonempty"):
            (self.drafts / self.assessment).write_text("")
            tools.register(context, rel, self.assessment, runner=success)
        record = tools.read_record(self.drafts / Path(rel).with_name(tools.RECORD))
        self.assertEqual(record["outcome"], "failed")

    def test_failed_missing_dependency_and_interrupted_checks_preserve_work(self):
        rel = self.staged()
        path = self.project / rel
        partial = path.parent / "partial.csv"
        for error in ("FileNotFoundError: missing-executable", "ModuleNotFoundError: missing dependency"):
            def fail(context, argv, cwd):
                partial.write_text("n,value\n1,2")
                return {**success(context, argv, cwd), "returncode": 1,
                        "outcome": "failed", "stderr": error}
            with self.assertRaisesRegex(tools.ToolError, "Declared check failed"):
                tools.register(self.context, rel, self.assessment, runner=fail)
            self.assertTrue(partial.exists())
            record = tools.read_record(self.drafts / Path(rel).with_name(tools.RECORD))
            self.assertIn(error, record["checks"][0]["stderr"])
            self.assertEqual(tools.discover(self.context, {})["tools"], [])
        def interrupt(*args):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            tools.register(self.context, rel, self.assessment, runner=interrupt)
        self.assertEqual(tools.read_record(self.drafts / Path(rel).with_name(tools.RECORD))["outcome"], "failed")
        def mutate(context, argv, cwd):
            (cwd / "method.py").write_text("changed during check")
            return success(context, argv, cwd)
        with self.assertRaisesRegex(tools.ToolError, "changed during checks"):
            tools.register(self.context, rel, self.assessment, runner=mutate)

    def test_failed_invocation_retains_receipt_partial_data_and_validation(self):
        rel, _ = self.register()
        def failed(context, argv, cwd):
            (cwd / "partial.json").write_text('{"partial": true}')
            return {**success(context, argv, cwd), "outcome": "failed", "returncode": 7,
                    "stderr": "ordinary runtime error"}
        result = tools.run(self.context, rel, ["partial.json"], runner=failed)
        self.assertEqual(result["returncode"], 7)
        note = (self.drafts / result["receipt"]).read_text()
        self.assertIn("ordinary runtime error", note)
        self.assertIn("[Output/input](../partial.json)", note)
        self.assertTrue((self.project / Path(rel).with_name("partial.json")).exists())
        self.assertEqual(len(tools.discover(self.context, {})["tools"]), 1)

    def test_authorization_scope_collisions_and_suspension(self):
        for source, rel in (("unknown", "work/tools/sum/tool.json"),
                            ("prior", "../outside"), ("prior", ".research_pipeline/private"),
                            ("prior", "/etc/passwd")):
            with self.subTest(source=source, path=rel), self.assertRaises(tools.ToolError):
                tools.stage(self.context, self.catalog, rel, "local", source)
        self.staged()
        with self.assertRaisesRegex(tools.ToolError, "already exists"):
            tools.stage(self.context, self.catalog, "work/tools/sum/tool.json", "local", "prior")
        for rel in ("work/tasks/foreign/tool.json", "starting_evidence/tool.json", "../escape"):
            with self.assertRaises(tools.ToolError):
                tools.register(self.context, rel, self.assessment, runner=success)
        (self.project / "work/link").symlink_to(self.prior, target_is_directory=True)
        with self.assertRaisesRegex(tools.ToolError, "Symlink"):
            tools.stage(self.context, {}, "work/link/work/tools/sum/tool.json", "new")
        child = {**self.context, "workspace": "work/tasks/task-a",
                 "excluded": ["work/tasks/task-a/inputs", "work/tasks/task-a/ASSIGNMENT.md"]}
        for rel in ("work/tools/local/tool.json", "work/tasks/task-b/tool.json",
                    "work/tasks/task-a/inputs/tool.json", "work/tasks/task-a/ASSIGNMENT.md"):
            with self.assertRaises(tools.ToolError):
                tools.own_path(child, rel)
        (self.control / "request.json").write_text('{"reason":"pause"}')
        with self.assertRaisesRegex(tools.ToolError, "Suspension"):
            tools.register(self.context, "work/tools/local/tool.json", self.assessment, runner=success)
        (self.control / "request.json").unlink()
        with self.assertRaisesRegex(tools.ToolError, "deadline"):
            tools.run({**self.context, "deadline": 0}, "work/tools/local/tool.json", [], runner=success)

    def test_copy_instability_preserves_failure_and_source_validation_is_only_evidence(self):
        original = tools.digest
        changed = False
        def changing(path):
            nonlocal changed
            result = original(path)
            if path.parent.name == "local" and not changed:
                changed = True
                (self.original.parent / "method.py").write_text("source changed")
            return result
        with patch.object(tools, "digest", side_effect=changing):
            with self.assertRaisesRegex(tools.ToolError, "Source changed"):
                self.staged()
        self.assertEqual(json.loads((self.project / "work/tools/local/SOURCE.json").read_text())["outcome"], "failed")
        # A real record from a source environment is discoverable, but never local authorization.
        source_drafts = self.prior / "drafts"
        assessment = "work/tools/sum/USE.md"
        (source_drafts / assessment).parent.mkdir(parents=True)
        (source_drafts / assessment).write_text("# Source scope\nFinite sums only.")
        context = {**self.context, "project": str(self.prior), "drafts": str(source_drafts),
                   "activation": "source", "excluded": []}
        tools.register(context, "work/tools/sum/tool.json", assessment, runner=success)
        workspace.publish_drafts(self.prior, source_drafts, {}, [])
        found = tools.discover(self.context, self.catalog)["tools"]
        self.assertEqual(found[0]["source"], "prior")
        self.assertIn("require local validation", found[0]["qualification"])
        staged = tools.stage(self.context, self.catalog, "work/tools/sum/tool.json", "another", "prior")
        with self.assertRaises((tools.ToolError, OSError)):
            tools.run(self.context, staged["description"], [], runner=success)

    def test_descriptor_change_between_parsing_and_hashing_cannot_validate_other_commands(self):
        rel = self.staged()
        original = tools.digest
        changed = False
        def change(path):
            nonlocal changed
            if path.name == "tool.json" and not changed:
                changed = True
                description = json.loads(path.read_text())
                description["invocation"] = ["unchecked-command"]
                path.write_text(json.dumps(description))
            return original(path)
        with patch.object(tools, "digest", side_effect=change):
            with self.assertRaisesRegex(tools.ToolError, "description changed"):
                tools.register(self.context, rel, self.assessment, runner=success)
        record = tools.read_record(self.drafts / Path(rel).with_name(tools.RECORD))
        self.assertEqual(record["outcome"], "failed")

    def test_context_mounts_effective_deadline_and_polling(self):
        session = self.project / ".research_pipeline/session"
        session.mkdir()
        config = isolation.Config(deadline=time.monotonic() + 1)
        polls = []
        config.on_poll = lambda research=False: polls.append(research)
        tools.configure(config, self.project, session, "owner")
        value = json.loads(config.tool_context.read_text())
        self.assertEqual(value["deadline"], config.deadline)
        self.assertEqual(value["activation"], "owner")
        self.assertTrue(polls)
        command = isolation.bubblewrap_command(self.project, ["true"], tool_context=config.tool_context)
        self.assertIn("/run/research-tools.py", command)
        self.assertIn("/run/research-tools.json", command)
        config.on_poll = lambda research=False: "pause"
        with self.assertRaises(isolation.RequestedStop):
            tools.configure(config, self.project, session, "new")

    def test_public_helper_argument_boundary(self):
        def read(path):
            return self.context if path.name == "research-tools.json" else {}
        with patch.object(tools, "read_json", side_effect=read), \
             patch.object(tools, "run", return_value={"outcome": "successful"}) as run, \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(tools.main(["run", "work/tools/local/tool.json", "--", "--output", "new.json"]), 0)
            self.assertEqual(run.call_args.args[-1], ["--output", "new.json"])
            self.assertEqual(tools.main(["run", "work/tools/local/tool.json", "extra"]), 2)

    def test_user_local_inputs_can_be_discovered_and_copied_but_not_registered_in_place(self):
        supplied = tool_fixture(self.project / "starting_evidence/user-tool")
        before = supplied.read_bytes()
        candidate = tools.discover(self.context, {}, candidates=True)["tools"][0]
        self.assertEqual(candidate["path"], "starting_evidence/user-tool/tool.json")
        self.assertFalse(candidate["eligible"])
        with self.assertRaisesRegex(tools.ToolError, "own working copy"):
            tools.register(self.context, candidate["path"], self.assessment, runner=success)
        staged = tools.stage(self.context, {}, candidate["path"], "input-copy")
        self.assertEqual(staged["source"]["origin"], "user")
        self.assertEqual(supplied.read_bytes(), before)
        with self.assertRaisesRegex(tools.ToolError, "scientific input"):
            tools.stage(self.context, {}, "AGENTS.md", "bad")

    def test_missing_executable_observation_and_no_launch_after_suspension(self):
        with patch.object(tools.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(tools.ToolError, "admitted scientific job"):
                tools.execute(self.context, ["unavailable"], self.project / "work")
            launch.assert_not_called()
        self.addCleanup(patch.stopall)
        patch.object(tools, "read_json", return_value={**self.context, "job_id": "execution-double"}).start()
        with patch.object(tools.subprocess, "Popen", side_effect=FileNotFoundError("missing executable")) as launch:
            result = tools.execute(self.context, ["unavailable"], self.project / "work")
            self.assertEqual(result["outcome"], "failed")
            self.assertIn("FileNotFoundError", result["error"])
            launch.assert_called_once()
        with patch.object(tools.subprocess, "Popen") as launch:
            (self.control / "request.json").write_text("{}")
            with self.assertRaisesRegex(tools.ToolError, "Suspension"):
                tools.execute(self.context, ["unavailable"], self.project / "work")
            launch.assert_not_called()

    def test_foreground_completion_does_not_wait_for_inherited_pipe_eof(self):
        """Engineering pipe/process doubles; no supplied scientific code is executed."""
        native_popen = subprocess.Popen
        for code in (0, 7):
            with self.subTest(returncode=code):
                out_read, out_write = os.pipe()
                err_read, err_write = os.pipe()
                writers = [out_write, err_write]
                # Double a detached descendant holding both output descriptors.
                # This test owns/reaps it, just as the service owns actual descendants.
                holder = native_popen([sys.executable, "-c", "import time; time.sleep(30)"],
                    stdout=out_write, stderr=err_write, start_new_session=True)
                streams = []
                def spawn(argv, **kwargs):
                    fixture = ("import sys\nprint('foreground output', flush=True)\n"
                               "print('foreground diagnostic', file=sys.stderr, flush=True)\n"
                               f"raise SystemExit({code})\n")
                    process = native_popen([sys.executable, "-c", fixture],
                        cwd=kwargs["cwd"], stdout=out_write, stderr=err_write,
                        start_new_session=kwargs["start_new_session"])
                    process.stdout = os.fdopen(out_read, "rb")
                    process.stderr = os.fdopen(err_read, "rb")
                    streams.extend((process.stdout, process.stderr))
                    for fd in writers:
                        os.close(fd)
                    writers.clear()
                    return process
                try:
                    began = time.monotonic()
                    context = {**self.context, "deadline": began + 3}
                    with patch.object(tools.subprocess, "Popen", side_effect=spawn), \
                         patch.object(tools, "read_json", return_value={**context, "job_id": "execution-double"}):
                        result = tools.execute(context, ["engineering-tool-double"], self.project / "work")
                    self.assertLess(time.monotonic() - began, 2)
                    self.assertEqual(result["returncode"], code)
                    self.assertEqual(result["outcome"], "successful" if code == 0 else "failed")
                    self.assertIn("foreground output", result["stdout"])
                    self.assertIn("foreground diagnostic", result["stderr"])
                    self.assertTrue(result["output_drain_incomplete"])
                    self.assertTrue(result["stdout_clipped"])
                    self.assertTrue(result["stderr_clipped"])
                    self.assertIsNone(holder.poll(), "Pipe capture must leave detached cleanup to its service owner")
                finally:
                    holder.kill()
                    holder.wait(timeout=5)
                    for stream in streams:
                        stream.close()
                    if not streams:
                        os.close(out_read)
                        os.close(err_read)
                    for fd in writers:
                        os.close(fd)

    def test_malformed_validation_records_do_not_hide_healthy_local_or_reference_tools(self):
        local_rel, local_record = self.register()
        source_drafts = self.prior / "drafts"
        assessment = "work/tools/sum/USE.md"
        (source_drafts / assessment).parent.mkdir(parents=True)
        (source_drafts / assessment).write_text("# Source scope\nFinite sums only.")
        source_context = {**self.context, "project": str(self.prior),
                          "drafts": str(source_drafts), "activation": "source", "excluded": []}
        source_record = tools.register(source_context, "work/tools/sum/tool.json", assessment, runner=success)
        workspace.publish_drafts(self.prior, source_drafts, {}, [])
        broken_rel = "work/tools/broken/tool.json"
        tool_fixture(self.project / Path(broken_rel).parent)
        tool_fixture(self.prior / Path(broken_rel).parent)
        local_path = self.drafts / Path(broken_rel).with_name(tools.RECORD)
        local_path.parent.mkdir(parents=True)
        source_path = self.prior / Path(broken_rel).with_name(tools.RECORD)
        variants = [[], None, 3, "invalid",
                    {"checks": None}, {"checks": {}}, {"checks": [[]]}, {"checks": [None]},
                    {"checks": ["invalid"]},
                    {"checks": [{**local_record["checks"][0], "argv": "python3 check.py"}]},
                    {"checks": [{**local_record["checks"][0], "returncode": False}]},
                    {"assessment": []}, {"activation": []}, {"version": True}]
        for malformed in variants:
            with self.subTest(record=malformed):
                for path, valid in ((local_path, local_record), (source_path, source_record)):
                    value = {**valid, **malformed} if isinstance(malformed, dict) else malformed
                    path.write_text(f"{tools.MARKER}```json\n{json.dumps(value)}\n```{tools.END}\n")
                    with self.assertRaisesRegex(tools.ToolError, "record|check|assessment|activation|version"):
                        tools.read_record(path)
                with self.assertRaises(tools.ToolError):
                    tools.registration(self.context, self.project / broken_rel,
                                       tools.load_description(self.project / broken_rel))
                listed = tools.discover(self.context, self.catalog)["tools"]
                self.assertEqual({(t["source"], t["path"]) for t in listed},
                                 {(None, local_rel), ("prior", "work/tools/sum/tool.json")})
                candidates = tools.discover(self.context, self.catalog, candidates=True)["tools"]
                broken = [t for t in candidates if t["path"] == broken_rel]
                self.assertEqual(len(broken), 2)
                self.assertTrue(all(not t["eligible"] and t["reason"] for t in broken))

    def test_live_evidence_requires_executed_helpers_and_resolved_convergence(self):
        from tests.test_m4_live import standalone, numerical_observations
        import math
        for command in ("cat <<'PY'\npython3 /run/research-tools.py register work/tool.json\nPY",
                        "python3 -c 'print(\"/run/research-tools.py run\")'",
                        "python3 /run/research-tools.py list && echo success",
                        "sh -c 'python3 /run/research-tools.py list; true'"):
            self.assertEqual(standalone(command), [])
        self.assertEqual(standalone("bash -lc 'python3 /run/research-tools.py list --candidates'"),
                         ["/run/research-tools.py", "list", "--candidates"])
        # Engineering oracle fixture, never supplied to the actual researcher.
        rows = [{"a": a, "n": n, "estimate": 2 * math.pi * a / (a*a - 1)**1.5}
                for a in (1.01, 1.1, 2.0) for n in (16, 32, 64, 128, 256, 512)]
        data = self.root / "grid.json"
        data.write_text(json.dumps({"rows": rows}))
        with self.assertRaisesRegex(AssertionError, "convergence"):
            numerical_observations(data)  # An answer substituted for sums has no grid error.
        rows[0]["estimate"] *= 1.05
        data.write_text(json.dumps({"rows": rows}))
        self.assertEqual(len(numerical_observations(data)[0]), 18)
        rows[-1]["estimate"] *= 1.1
        data.write_text(json.dumps({"rows": rows}))
        with self.assertRaisesRegex(AssertionError, "oracle"):
            numerical_observations(data)
