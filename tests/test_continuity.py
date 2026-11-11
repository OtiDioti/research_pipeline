"""Consequential checkpoint tests with explicit backend doubles, not live science."""
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tests import use_checkout, record_job

use_checkout()
from research_pipeline import cli, codex, isolation, references, workspace, tools


HANDOFF = """# Primary handoff
Logical researcher: primary

## Objective
Study numerical convergence.
## Completed
Computed a preliminary reference.
## Artifacts
[Plan](../work/PLAN.md)
[Data](../work/data.csv)
## Assumptions
Deterministic arithmetic.
## Unresolved
Rate uncertainty; no active computation.
## Next action
Compare asymptotic rates with saved data.
"""


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        (self.project / "starting_evidence").mkdir(parents=True)
        (self.project / "starting_evidence/RESEARCH_QUESTIONS.md").write_text("Study A and B.")
        (self.project / "AGENTS.md").write_text("Use deterministic calculations.")
        self.prompts, self.launches = [], []

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([args[0], str(self.project), *args[1:]])
        return code, out.getvalue() + err.getvalue()

    def state(self):
        return json.loads((self.project / ".research_pipeline/run.json").read_text())

    def save(self, state):
        workspace.write_state(self.project, state)

    @contextmanager
    def backend(self, during=None, handoff=HANDOFF, bad_draft=False, cleanup=True, identity=True,
                usage=True, failed=False, commands=True):
        @contextmanager
        def auth(project):
            yield project / ".research_pipeline"
        def execute(config, project, argv, stdin, recorder, auth_home):
            saved = self.state()
            self.assertTrue(saved["service_attempted"], "Launch intent must precede spawn")
            self.assertEqual(saved["service"], config.unit)
            self.prompts.append(stdin)
            self.launches.append((config.unit, config.wall_seconds, config.deadline - time.monotonic()))
            if identity:
                native = f"native-{len(self.prompts)}"
                recorder("stdout", (json.dumps({"type": "thread.started", "thread_id": native}) + "\n").encode())
                self.assertEqual(self.state()["native_session_id"], native)
            for name in workspace.MANAGED:
                (config.drafts / name).mkdir(exist_ok=True)
            (config.drafts / "work/PLAN.md").write_text("# Plan\nRevised according to current questions.\n")
            (config.drafts / "outputs/REPORT.md").write_text("# Preliminary report\n[Data](../work/data.csv)\n")
            (config.drafts / "sources/LITERATURE.md").write_text("# Literature\nSource not yet checked.\n")
            (config.drafts / "RESEARCH_STATUS.md").write_text("# Scientific status\nProgress and next action.\n")
            if handoff is not None:
                (config.drafts / "handoffs/primary.md").write_text(handoff)
            if bad_draft:
                (config.drafts / "run.json").write_text("forbidden")
            (project / "work/data.csv").write_text("n,value\n1,2\n")
            if commands:
                record_job(config)
                recorder("stdout", b'{"type":"item.completed","item":{"type":"command_execution","exit_code":0}}\n')
            if usage:
                for n in (10, 20):
                    recorder("stdout", (json.dumps({"type": "turn.completed", "usage": {
                        "input_tokens": n, "cached_input_tokens": n // 2, "output_tokens": 3}}) + "\n").encode())
            if during:
                during(config)
            return isolation.ExecutionResult(9 if failed else 0, cleanup_ok=cleanup)
        with patch.object(codex, "verify_backend", return_value={"version": "double"}), \
             patch.object(isolation, "preflight", return_value={"probe": "double"}), \
             patch.object(codex, "private_auth", auth), \
             patch.object(isolation, "run_isolated", execute):
            yield

    def start(self):
        with self.backend():
            code, out = self.call("start", "--wall-seconds", "60")
        self.assertEqual(code, 0, out)
        return self.state()

    def test_references_resume_qualified_reuse_and_human_edits(self):
        prior = Path(self.temp.name) / "prior"
        prior.mkdir()
        (prior / "result.md").write_text("# Preliminary result\nAssumes positive n.")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["reference", "add", str(self.project), "prior", str(prior)]), 0)
        reuse = ("# Qualified reuse\nSource prior/result.md, preliminary, no independent check. "
                 "Positive n is applicable here; sensitivity remains uncertain.")
        catalogs = []
        def write_reuse(config):
            catalogs.append(json.loads(config.reference_catalog.read_text()))
            if len(catalogs) > 1:
                note = self.project / "sources/REUSE.md"
                note.write_text(note.read_text() + "\nHuman: edited during this session.")
            (config.drafts / "sources/REUSE.md").write_text(reuse)
        with self.backend(during=write_reuse, handoff=HANDOFF + "\n[Reuse](../sources/REUSE.md)\n"):
            code, out = self.call("start", "--wall-seconds", "60")
        self.assertEqual(code, 0, out)
        first = self.state()
        snapshot = (self.project / first["checkpoint"]["intake"]).read_text()
        self.assertIn(str(prior), snapshot)
        self.assertIn("sources/REUSE.md", first["checkpoint"]["artifacts"])
        (self.project / "sources/REUSE.md").write_text(reuse + "\nHuman: applicability must be narrowed.")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["reference", "remove", str(self.project), "prior"]), 0)
            self.assertEqual(cli.main(["reference", "add", str(self.project), "updated", str(prior)]), 0)
        with self.backend(during=write_reuse, handoff=HANDOFF + "\n[Reuse](../sources/REUSE.md)\n"):
            code, out = self.call("resume")
        self.assertEqual(code, 4, out)  # Preserved edit requires human reconciliation.
        self.assertEqual(set(catalogs[0]), {"prior"})
        self.assertEqual(set(catalogs[1]), {"updated"})
        self.assertEqual(catalogs[1]["updated"]["path"], "/references/updated")
        second = self.state()
        self.assertEqual(first["limits"], second["limits"])
        self.assertGreater(second["active_seconds"], first["active_seconds"])
        self.assertEqual(second["usage_totals"]["input_tokens"], 60)
        self.assertIn(".research_pipeline/references.json", self.prompts[-1])
        self.assertIn("sources/REUSE.md", self.prompts[-1])
        self.assertIn("Human:", (self.project / "sources/REUSE.md").read_text())
        self.assertTrue(any(p["path"] == "sources/REUSE.md" for p in second["pending_reconciliation"]))
        self.assertEqual((prior / "result.md").read_text(), "# Preliminary result\nAssumes positive n.")

    def test_tool_records_resume_revalidation_and_concurrent_human_edit(self):
        from tests.test_tools import tool_fixture, success
        rel = "work/tools/sum/tool.json"
        assessment = "work/tools/sum/USE.md"
        seen = []
        def tool_work(config):
            context = json.loads(config.tool_context.read_text())
            self.assertEqual(context["deadline"], config.deadline)
            self.assertEqual(context["activation"], self.state()["activation_id"])
            context.update(project=str(self.project), drafts=str(config.drafts),
                           control=str(config.control))
            seen.append(context["activation"])
            if len(seen) == 1:
                tool_fixture(self.project / "work/tools/sum")
            else:
                with self.assertRaisesRegex(tools.ToolError, "Fresh activation"):
                    tools.run(context, rel, [], runner=success)
                validation = self.project / "work/tools/sum/VALIDATION.md"
                validation.write_text(validation.read_text() + "\nHuman: limit scope to positive finite inputs.")
            use = config.drafts / assessment
            use.parent.mkdir(parents=True, exist_ok=True)
            use.write_text("# Intended use\nElementary checks for finite sums; overflow untested.")
            tools.register(context, rel, assessment, runner=success)
            tools.run(context, rel, [], runner=success)
        handoff = HANDOFF + "\n[Tool validation](../work/tools/sum/VALIDATION.md)\n"
        with self.backend(during=tool_work, handoff=handoff):
            code, out = self.call("start", "--wall-seconds", "60")
        self.assertEqual(code, 0, out)
        first = self.state()
        self.assertIn("work/tools/sum/VALIDATION.md", first["checkpoint"]["artifacts"])
        self.assertTrue((self.project / "work/tools/sum/FOLDER_CONTENT.md").exists())
        with self.backend(during=tool_work, handoff=handoff):
            code, out = self.call("resume")
        self.assertEqual(code, 4, out)
        second = self.state()
        self.assertNotEqual(*seen)
        self.assertEqual(first["limits"], second["limits"])
        self.assertGreater(second["active_seconds"], first["active_seconds"])
        self.assertIn("Human:", (self.project / "work/tools/sum/VALIDATION.md").read_text())
        self.assertTrue(any(p["path"] == "work/tools/sum/VALIDATION.md"
                            for p in second["pending_reconciliation"]))

    def test_authorization_refuses_mutation_until_stale_service_cleanup_confirmed(self):
        state = self.start()
        state["cleanup_ok"] = False
        self.save(state)
        prior = Path(self.temp.name) / "prior"
        prior.mkdir()
        with patch.object(isolation, "stop_service", return_value=False), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["reference", "add", str(self.project), "prior", str(prior)]), 2)
        self.assertFalse((self.project / ".research_pipeline/references.json").exists())

    def test_resume_reference_timeout_consumes_remaining_budget_before_launch(self):
        state = self.start()
        prior = Path(self.temp.name) / "slow-prior"
        (prior / "outputs").mkdir(parents=True)
        for n in range(20):
            (prior / f"outputs/result-{n}.md").write_text("# Preliminary evidence\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["reference", "add", str(self.project), "prior", str(prior)]), 0)
        state["active_seconds"] = 55
        state["remaining_active_seconds"] = 5
        self.save(state)
        science = workspace.science_fingerprints(self.project)
        inputs = workspace.fingerprints(self.project)
        ordinary = references.ordinary
        with patch.object(cli.time, "monotonic", return_value=100) as clock:
            def slow(path):
                if path.is_relative_to(prior):
                    self.assertIn("resume_preparation_pending", self.state())
                    clock.return_value += 1
                return ordinary(path)
            with patch.object(references, "ordinary", side_effect=slow), \
                 patch.object(codex, "verify_backend") as backend:
                code, out = self.call("resume")
                self.assertEqual(code, 124, out)
                backend.assert_not_called()
            saved = self.state()
            self.assertEqual(saved["state"], "timed_out")
            self.assertEqual(saved["active_seconds"], 60)
            self.assertEqual(saved["remaining_active_seconds"], 0)
            self.assertEqual(saved["resume_preparation_seconds"], 5)
            self.assertNotIn("resume_preparation_pending", saved)
            self.assertEqual(saved["sessions"], state["sessions"])
            self.assertEqual(saved["usage_totals"], state["usage_totals"])
            with patch.object(codex, "verify_backend") as backend:
                code, out = self.call("resume")
                self.assertEqual(code, 2, out)
                self.assertIn("exhausted", out)
                backend.assert_not_called()
        self.assertEqual(science, workspace.science_fingerprints(self.project))
        self.assertEqual(inputs, workspace.fingerprints(self.project))

    def test_resume_preparation_failure_and_interrupt_are_charged_and_retryable(self):
        self.start()
        for failure, outcome, expected in ((references.ReferenceError("malformed registry"), "failed", 2),
                                           (KeyboardInterrupt(), "interrupted", 130)):
            with self.subTest(outcome=outcome):
                before = self.state()
                with patch.object(cli.time, "monotonic", return_value=100) as clock:
                    def fail(project):
                        self.assertIn("resume_preparation_pending", self.state())
                        clock.return_value += 3
                        raise failure
                    with patch.object(references, "load_registry", side_effect=fail), \
                         patch.object(codex, "verify_backend") as backend:
                        code, out = self.call("resume")
                        self.assertEqual(code, expected, out)
                        backend.assert_not_called()
                saved = self.state()
                self.assertEqual(saved["state"], outcome)
                self.assertAlmostEqual(saved["active_seconds"], before["active_seconds"] + 3)
                self.assertEqual(saved["sessions"], before["sessions"])
                self.assertEqual(saved["usage_totals"], before["usage_totals"])
                self.assertNotIn("resume_preparation_pending", saved)
                report = cli.inspect_project(self.project)["budget_report"]
                self.assertEqual(report["configured_limits"], before["limits"])
                self.assertEqual(report["active_seconds_observed"], saved["active_seconds"])
                self.assertEqual(report["remaining_seconds_observed"], saved["remaining_active_seconds"])
        before = self.state()
        load = references.load_registry
        with patch.object(cli.time, "monotonic", return_value=200) as clock:
            def slow(project):
                clock.return_value += 2
                return load(project)
            with self.backend(), patch.object(references, "load_registry", side_effect=slow):
                code, out = self.call("resume")
                self.assertEqual(code, 0, out)
        saved = self.state()
        self.assertAlmostEqual(saved["active_seconds"], before["active_seconds"] + 4)
        self.assertEqual(saved["sessions"][-1]["active_seconds"], 4)
        self.assertNotIn("resume_preparation_pending", saved)

    def test_killed_resume_preparation_recovers_its_interval_once_without_old_service_cleanup(self):
        before = self.start()
        script = r'''
import os, signal, sys
from pathlib import Path
from unittest.mock import patch
from research_pipeline import cli
def crash(project, *args):
    state = cli.load_state(project)
    assert state["resume_preparation_pending"]["started_monotonic"] == 100
    assert state["cleanup_ok"]
    os.kill(os.getpid(), signal.SIGKILL)
with patch.object(cli.time, "monotonic", return_value=100), \
     patch.object(cli, "continuation_inputs", side_effect=crash):
    cli.main(["resume", sys.argv[1]])
'''
        process = subprocess.run([sys.executable, "-c", script, str(self.project)],
                                 capture_output=True, timeout=10)
        self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
        saved = self.state()
        self.assertIn("resume_preparation_pending", saved)
        with patch.object(cli.time, "monotonic", return_value=105), \
             patch.object(isolation, "stop_service") as stop:
            with workspace.acquire_project_lock(self.project):
                cli.recover_owner(self.project, saved)
            stop.assert_not_called()
            recovered = self.state()
            self.assertAlmostEqual(recovered["active_seconds"], before["active_seconds"] + 5)
            self.assertEqual(recovered["resume_preparation_seconds"], 5)
            self.assertEqual(recovered["sessions"], before["sessions"])
            self.assertNotIn("resume_preparation_pending", recovered)
            with workspace.acquire_project_lock(self.project):
                cli.recover_owner(self.project, recovered)
            self.assertEqual(self.state(), recovered)

    def test_resume_reloads_direction_keeps_identity_and_cumulative_limits(self):
        first = self.start()
        first_log = self.project / first["sessions"][0]["logs"] / "backend.jsonl"
        log_before = first_log.read_bytes()
        data_before = (self.project / "work/data.csv").read_bytes()
        human = Path(self.temp.name) / "direction.md"
        human.write_text("Remove A; revise B; add C.")
        self.assertEqual(self.call("redirect", "--questions-file", str(human))[0], 0)
        human.write_text("Correct the boundary assumption.")
        self.assertEqual(self.call("feedback", "--file", str(human))[0], 0)
        self.assertEqual(self.call("feedback", "--file", str(human))[0], 0)
        (self.project / "AGENTS.md").unlink()
        # Scientific symlinks and FIFOs must not prevent intake or be opened.
        (self.project / "work/link").symlink_to("/unavailable")
        import os
        os.mkfifo(self.project / "work/pending.md")
        with self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        second = self.state()
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(second["logical_researcher_id"], "primary")
        self.assertNotEqual(first["activation_id"], second["activation_id"])
        self.assertNotEqual(first["native_session_id"], second["native_session_id"])
        self.assertEqual(first["limits"], second["limits"])
        self.assertLess(self.launches[-1][2], 60)
        self.assertGreater(second["active_seconds"], first["active_seconds"])
        self.assertEqual(second["usage_totals"], {
            "input_tokens": 60, "cached_input_tokens": 30, "output_tokens": 12})
        self.assertTrue(second["usage_complete"])
        self.assertEqual(log_before, first_log.read_bytes())
        self.assertEqual(data_before, (self.project / "work/data.csv").read_bytes())
        for text in ("Study A and B.", "Remove A; revise B; add C.", "Correct the boundary assumption.",
                     "Use deterministic calculations.", "ADDED", "REMOVED", HANDOFF.strip()):
            # Continuation JSON escapes newlines; substantive text must still be present.
            self.assertIn(text.replace("\n", "\\n") if text == HANDOFF.strip() else text, self.prompts[-1])
        self.assertFalse((self.project / "starting_evidence/FOLDER_CONTENT.md").exists())

    def test_human_notes_status_and_indexes_are_preserved_when_incorporated(self):
        self.start()
        for rel in ("work/PLAN.md", "RESEARCH_STATUS.md", "work/FOLDER_CONTENT.md"):
            with (self.project / rel).open("a") as stream:
                stream.write("\nHuman correction: retain endpoint uncertainty.\n")
        (self.project / "outputs/REPORT.md").unlink()
        with self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        preserved = [p for p in (self.project / "handoffs/preserved").glob("*.md")
                     if p.name != "FOLDER_CONTENT.md"]
        self.assertEqual(len(preserved), 3)
        self.assertTrue(all("Human correction" in p.read_text() for p in preserved))
        self.assertIn("outputs/REPORT.md", self.prompts[-1])
        self.assertIn("external_markdown_changes_or_deletions", self.prompts[-1])
        for directory in (self.project / "handoffs", self.project / "handoffs/preserved"):
            self.assertTrue((directory / "FOLDER_CONTENT.md").is_file())
        self.assertIn("Preserved edited index", (self.project / "work/FOLDER_CONTENT.md").read_text())

    def test_edits_and_deletion_during_execution_preserve_canonical_state(self):
        first = self.start()
        def edit(config):
            (self.project / "work/PLAN.md").write_text("# Human plan\nKeep this correction.")
            (self.project / "outputs/REPORT.md").unlink()
            (self.project / "RESEARCH_STATUS.md").write_text("# Human status\nKeep this.")
            (self.project / "work/UNTARGETED.md").write_text("# Human observation\nReview this separately.")
        with self.backend(during=edit):
            code, out = self.call("resume")
        self.assertEqual(code, 4, out)
        self.assertEqual((self.project / "work/PLAN.md").read_text(), "# Human plan\nKeep this correction.")
        self.assertFalse((self.project / "outputs/REPORT.md").exists())
        self.assertEqual((self.project / "RESEARCH_STATUS.md").read_text(), "# Human status\nKeep this.")
        state = self.state()
        self.assertIn("work/UNTARGETED.md", state["pending_human_changes"])
        self.assertEqual(len(state["pending_reconciliation"]), 3)
        for conflict in state["pending_reconciliation"]:
            self.assertTrue((self.project / conflict["proposal"]).is_file())
        # The handoff references the plan and data, so this remains a valid partial checkpoint.
        self.assertNotEqual(first["checkpoint"]["id"], state["checkpoint"]["id"])
        with self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        self.assertIn("pending_reconciliation", self.prompts[-1])
        self.assertIn("work/UNTARGETED.md", self.prompts[-1])
        saved = "\n".join(p.read_text() for p in (self.project / "handoffs/preserved").glob("*.md"))
        self.assertIn("# Human plan", saved)
        self.assertIn("# Human status", saved)

    def test_invalid_drafts_or_handoff_retain_last_checkpoint_and_fallback(self):
        first = self.start()
        for kwargs in ({"bad_draft": True}, {"handoff": "# Inadequate summary"}, {"handoff": None}):
            with self.subTest(kwargs=kwargs), self.backend(**kwargs):
                code, out = self.call("resume")
                self.assertEqual(code, 4, out)
                self.assertEqual(self.state()["checkpoint"], first["checkpoint"])
        with self.backend():
            self.assertEqual(self.call("resume")[0], 0)
        state = self.state()
        (self.project / state["checkpoint"]["handoff"]).write_text("# Damaged newest checkpoint")
        with self.backend():
            self.assertEqual(self.call("resume")[0], 0)
        self.assertIn(first["checkpoint"]["id"], self.prompts[-1])

    def test_stale_launch_cleanup_precedes_new_work_and_retains_deadline_charge(self):
        state = self.start()
        state.update(state="running", cleanup_ok=None, accounting_pending=True,
                     activation_started_epoch=time.time() - 5, activation_allowance=50)
        self.save(state)
        with patch.object(isolation, "stop_service", return_value=False) as stop, self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 2, out)
        self.assertEqual(len(self.prompts), 1, "Uncertain cleanup must prevent launch")
        stop.assert_called_once_with(state["service"])
        with patch.object(isolation, "stop_service", return_value=True) as stop, self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        self.assertGreaterEqual(self.state()["active_seconds"], 5)
        self.assertFalse(self.state()["usage_complete"])
        self.assertIn("Controller lost", self.prompts[-1])
        self.assertLess(self.launches[-1][2], 55)
        stop.assert_called_once_with(state["service"])

    def test_cleanup_failure_dominates_input_changes_and_does_not_publish(self):
        self.start()
        previous = (self.project / "work/PLAN.md").read_bytes()
        def edit(config):
            (self.project / "starting_evidence/RESEARCH_QUESTIONS.md").write_text("Changed during run.")
            (config.drafts / "work/PLAN.md").write_text("# New draft must remain private")
        with self.backend(during=edit, cleanup=False):
            code, out = self.call("resume")
        self.assertEqual(code, 4, out)
        self.assertEqual(self.state()["state"], "failed")
        self.assertIn("cleanup", self.state()["reason"].lower())
        self.assertFalse(self.state()["inputs_unchanged"])
        self.assertEqual(previous, (self.project / "work/PLAN.md").read_bytes())

    def check_delayed_cleanup_accounting(self, observed):
        first = self.start()
        with patch.object(cli.time, "monotonic", return_value=1000) as clock, \
             patch.object(cli.time, "time", return_value=2000):
            def elapsed(config):
                clock.return_value = 1005
            with self.backend(during=elapsed, cleanup=False):
                code, out = self.call("resume")
        self.assertEqual(code, 4, out)
        failed = self.state()
        self.assertTrue(failed["accounting_pending"])
        self.assertEqual(failed["activation_charged_seconds"], 5)
        self.assertAlmostEqual(failed["active_seconds"], first["active_seconds"] + 5)

        with patch.object(cli.time, "monotonic", return_value=1010), \
             patch.object(cli.time, "time", return_value=2010), \
             patch.object(isolation, "stop_service", return_value=False):
            self.assertEqual(self.call("resume")[0], 2)
        self.assertTrue(self.state()["accounting_pending"])
        self.assertEqual(self.state()["active_seconds"], failed["active_seconds"])

        props = {"InactiveEnterTimestampMonotonic": "1012000000"} if observed else {}
        with patch.object(cli.time, "monotonic", return_value=1012), \
             patch.object(cli.time, "time", return_value=2012), \
             patch.object(isolation, "stop_service", return_value=True), \
             patch.object(isolation, "service_properties", return_value=props), self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        recovered = self.state()
        self.assertFalse(recovered["accounting_pending"])
        self.assertAlmostEqual(recovered["active_seconds"], first["active_seconds"] + 12)
        self.assertEqual(recovered["sessions"][-2]["active_seconds"], 12)
        self.assertAlmostEqual(self.launches[-1][2], 60 - first["active_seconds"] - 12)
        # Rechecking quiescent ownership must not charge the interval again.
        cli.recover_owner(self.project, recovered)
        self.assertEqual(recovered["active_seconds"], self.state()["active_seconds"])
        # A longer residual interval exhausts the original allowance; it must
        # never become extra time for a new activation.
        self.save(failed)
        props = {"InactiveEnterTimestampMonotonic": "1200000000"} if observed else {}
        launches = len(self.launches)
        with patch.object(cli.time, "monotonic", return_value=1200), \
             patch.object(cli.time, "time", return_value=2200), \
             patch.object(isolation, "stop_service", return_value=True), \
             patch.object(isolation, "service_properties", return_value=props), self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 2, out)
        self.assertIn("exhausted", out)
        self.assertEqual(len(self.launches), launches)
        self.assertEqual(self.state()["active_seconds"], 60)
        self.assertEqual(self.state()["remaining_active_seconds"], 0)
        self.assertFalse(self.state()["accounting_pending"])

    def test_failed_cleanup_charges_residual_work_with_observed_inactivity(self):
        self.check_delayed_cleanup_accounting(observed=True)

    def test_failed_cleanup_charges_residual_work_with_elapsed_time_fallback(self):
        self.check_delayed_cleanup_accounting(observed=False)

    def test_invalid_draft_entries_do_not_block_checkpoint_continuation(self):
        first = self.start()
        for kind in ("symlink", "fifo"):
            with self.subTest(kind=kind):
                invalid = []
                def corrupt(config):
                    path = config.drafts / "work/invalid.md"
                    if kind == "symlink":
                        path.symlink_to(self.project / "starting_evidence/RESEARCH_QUESTIONS.md")
                    else:
                        os.mkfifo(path)
                    invalid.append(path)
                with self.backend(during=corrupt):
                    code, out = self.call("resume")
                self.assertEqual(code, 4, out)
                self.assertIn("Checkpoint finalization failed", out)
                self.assertEqual(self.state()["checkpoint"], first["checkpoint"])
                workspace.read_intake(self.project)
                with self.backend():
                    code, out = self.call("resume")
                self.assertEqual(code, 0, out)
                self.assertIn(first["checkpoint"]["id"], self.prompts[-1])
                self.assertTrue(invalid[0].is_symlink() if kind == "symlink" else invalid[0].exists())
                first = self.state()

    def test_valid_partial_checkpoint_and_resume_without_repeating_computation(self):
        first = self.start()
        with self.backend(commands=False):
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["successful_commands"], first["successful_commands"])
        def partial(config):
            (config.drafts / "outputs/REPORT.md").unlink()
            (self.project / "outputs/REPORT.md").unlink()
        with self.backend(during=partial, commands=False, failed=True):
            code, out = self.call("resume")
        self.assertEqual(code, 4, out)
        self.assertEqual(self.state()["checkpoint"]["id"], self.state()["activation_id"])
        self.assertFalse((self.project / "outputs/REPORT.md").exists())
        with self.backend(commands=False):
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)

    def test_crash_accounting_prefers_observed_service_inactivity_on_same_boot(self):
        state = self.start()
        began = time.monotonic() - 50
        state.update(state="running", cleanup_ok=None, accounting_pending=True,
                     activation_started_epoch=time.time() - 50, activation_allowance=59,
                     activation_started_monotonic=began, boot_id=cli.boot_identity())
        self.save(state)
        with patch.object(isolation, "stop_service", return_value=True), \
             patch.object(isolation, "service_properties", return_value={
                 "InactiveEnterTimestampMonotonic": str(int((began + 3) * 1e6))}), self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        self.assertLess(self.state()["active_seconds"], 5)
        self.assertIn("observed service inactivity", self.state()["accounting_uncertainties"][-1])

    def test_resume_missing_telemetry_exhausted_limits_schema_and_competing_lock(self):
        self.start()
        with self.backend(identity=False, usage=False):
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        self.assertIsNone(self.state()["native_session_id"])
        self.assertFalse(self.state()["usage_complete"])
        with workspace.acquire_project_lock(self.project):
            self.assertEqual(self.call("resume")[0], 2)
            self.assertEqual(self.call("feedback", "--file",
                                       str(self.project / "AGENTS.md"))[0], 2)
        state = self.state()
        state["active_seconds"] = state["limits"]["wall_seconds"]
        self.save(state)
        self.assertIn("exhausted", self.call("resume")[1])
        state["schema_version"] = 1
        self.save(state)
        self.assertIn("Unsupported state schema", self.call("resume")[1])
        self.assertEqual(self.call("inspect")[0], 0)

    def test_missing_current_questions_does_not_destroy_checkpoint(self):
        state = self.start()
        (self.project / "starting_evidence/RESEARCH_QUESTIONS.md").unlink()
        self.assertEqual(self.call("resume")[0], 2)
        self.assertEqual(state["checkpoint"], self.state()["checkpoint"])
        self.assertTrue((self.project / state["checkpoint"]["handoff"]).is_file())
        replacement = Path(self.temp.name) / "restored.md"
        replacement.write_text("Continue only the revised B objective.")
        self.assertEqual(self.call("redirect", "--questions-file", str(replacement))[0], 0)
        with self.backend():
            self.assertEqual(self.call("resume")[0], 0)

    def test_controller_crash_from_real_process_persists_launch_and_recovers(self):
        """SIGKILL a real controller process at the launch boundary (backend double)."""
        import os
        import signal
        import subprocess
        import sys
        # Bootstrap saved science in this process, then lose the next owner.
        first = self.start()
        script = r'''
from contextlib import contextmanager
from pathlib import Path
import os, signal, sys
from unittest.mock import patch
from research_pipeline import cli, codex, isolation
@contextmanager
def auth(project):
    yield project / ".research_pipeline"
def crash(*args, **kwargs):
    # Leave both kinds of untrusted draft entry behind when the owner dies.
    os.mkfifo(args[0].drafts / "invalid.md")
    (args[0].drafts / "outside.md").symlink_to("/unavailable")
    args[4]("stdout", b'{"type":"thread.started","thread_id":"lost-native"}\n')
    args[4]("stdout", b'{"type":"turn.completed","usage":{"input_tokens":13,"output_tokens":7}}\n')
    os.kill(os.getpid(), signal.SIGKILL)
with patch.object(codex, "verify_backend", return_value={}), \
     patch.object(isolation, "preflight", return_value={}), \
     patch.object(codex, "private_auth", auth), \
     patch.object(isolation, "run_isolated", crash):
    cli.main(["resume", sys.argv[1]])
'''
        process = subprocess.run([sys.executable, "-c", script, str(self.project)],
                                 capture_output=True, timeout=10)
        self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
        crashed = self.state()
        self.assertEqual(crashed["state"], "running")
        self.assertTrue(crashed["service_attempted"])
        self.assertTrue(crashed["accounting_pending"])
        self.assertEqual(crashed["usage_totals"]["input_tokens"], 43)
        self.assertEqual(crashed["native_session_id"], "lost-native")
        self.assertEqual(crashed["checkpoint"]["id"], first["checkpoint"]["id"])
        with patch.object(isolation, "stop_service", return_value=False) as stop, self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 2, out)
        self.assertIn("cleanup could not be confirmed", out)
        stop.assert_called_once_with(crashed["service"])
        with patch.object(isolation, "stop_service", return_value=True) as stop, self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["usage_totals"]["input_tokens"], 73)
        stop.assert_called_once_with(crashed["service"])
        self.assertIn("interrupted", self.state()["sessions"][-2]["outcome"])
