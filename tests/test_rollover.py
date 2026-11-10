"""Checkpoint/session engineering doubles; not real Codex scientific evidence."""
from contextlib import contextmanager, redirect_stderr
import io
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from tests import test_continuity as fixtures

HANDOFF = fixtures.HANDOFF
from research_pipeline import cli, codex, isolation, workspace


class RolloverTests(unittest.TestCase):
    setUp = fixtures.ContinuityTests.setUp
    call = fixtures.ContinuityTests.call
    state = fixtures.ContinuityTests.state
    save = fixtures.ContinuityTests.save
    backend = fixtures.ContinuityTests.backend
    start = fixtures.ContinuityTests.start

    @contextmanager
    def sessions(self, first=None, second=None, count=1, identities=True, usage=True,
                 cleanup=True, startup_failure=False):
        """Use controlled session time, real checkpoint preparation and publication."""
        self.contexts = []
        self.auth_homes = []
        with patch.object(cli.time, "monotonic", return_value=1000) as clock:
            self.clock = clock

            @contextmanager
            def auth(project):
                with tempfile.TemporaryDirectory(dir=project / ".research_pipeline") as temp:
                    home = Path(temp)
                    (home / "auth.json").write_text("{}")
                    self.assertEqual([p.name for p in home.iterdir()], ["auth.json"])
                    self.auth_homes.append(home)
                    yield home

            def verify(config):
                clock.return_value += 2
                if startup_failure and self.contexts:
                    raise isolation.RuntimeUnavailable("Successor backend unavailable")
                return {"version": "engineering double"}

            def preflight(config, project):
                config.on_probe_launch(f"research-{uuid.uuid4().hex}.service")
                return {}

            def execute(config, project, command, prompt, recorder, auth_home):
                n = len(self.contexts)
                self.assertLess(n, count + 1, "Unexpected continuation loop")
                state = self.state()
                self.contexts.append((state, command, prompt, config.deadline))
                self.assertTrue(state["service_attempted"])
                self.assertAlmostEqual(config.deadline, min(1100, clock.return_value + 30))
                self.assertAlmostEqual(state["activation_deadline_epoch"] -
                                       state["activation_started_epoch"],
                                       config.deadline - state["activation_started_monotonic"])
                self.assertIn("--ephemeral", command)
                self.assertNotIn("resume", command)
                with self.assertRaises(workspace.ProjectBusy):
                    with workspace.acquire_project_lock(project):
                        pass
                if n:
                    previous = self.contexts[-2][0]
                    self.assertEqual(state["ownership_nonce"], previous["ownership_nonce"])
                    self.assertEqual(state["run_id"], previous["run_id"])
                    self.assertNotEqual(state["activation_id"], previous["activation_id"])
                    self.assertNotEqual(state["service"], previous["service"])
                    self.assertEqual(state["limits"], previous["limits"])
                    self.assertTrue((project / "handoffs/primary.md").exists())
                    self.assertFalse(self.auth_homes[-2].exists())
                    self.assertIn("Computed a preliminary reference.", prompt)
                    self.assertEqual((project / "work/data.csv").read_text(), "n,value\n1,2\n")
                    self.assertIn("Cumulative investigation limits", prompt)
                identity = identities(n) if callable(identities) else f"native-{n}" if identities else None
                if identity:
                    recorder("stdout", (json.dumps({"type": "thread.started", "thread_id": identity}) + "\n").encode())
                for name in workspace.MANAGED:
                    (config.drafts / name).mkdir(exist_ok=True)
                for rel, text in {
                    "work/PLAN.md": "# Plan\nAdapt to current intake; retain reference data.",
                    "outputs/REPORT.md": "# Preliminary result\n[Data](../work/data.csv)",
                    "sources/LITERATURE.md": "# Literature\nAccess not yet checked.",
                    "RESEARCH_STATUS.md": "# Status\nRate comparison remains.",
                    "handoffs/primary.md": HANDOFF,
                }.items():
                    (config.drafts / rel).write_text(text)
                if not n:
                    (project / "work/data.csv").write_text("n,value\n1,2\n")
                else:
                    (project / f"work/comparison-{n}.csv").write_text("n,error\n2,0.1\n")
                recorder("stdout", b'{"type":"item.completed","item":{"type":"command_execution","exit_code":0}}\n')
                if usage is True or callable(usage) and usage(n):
                    recorder("stdout", b'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}\n')
                if n < count:
                    controller = config.on_poll.__self__
                    clock.return_value = controller.rollover_at
                    self.assertIsNone(config.on_poll())
                    request = workspace.read_control(config.control / "request.json")
                    self.assertEqual(request["reason"], "rollover")
                    if first:
                        first(config, request, n)
                    else:
                        self.ack(config, request)
                    clock.return_value += 1
                elif second:
                    second(config)
                clock.return_value += 1
                return isolation.ExecutionResult(0, cleanup_ok=cleanup,
                    service_properties={"ControlGroup": f"/engineering/{config.unit}"})

            with patch.object(codex, "verify_backend", side_effect=verify), \
                 patch.object(codex, "private_auth", auth), \
                 patch.object(isolation, "preflight", side_effect=preflight), \
                 patch.object(isolation, "run_isolated", side_effect=execute), \
                 patch.object(isolation, "stop_service", return_value=True):
                yield

    def ack(self, config, request):
        workspace.atomic_text(config.response / "ready.json",
                              json.dumps({**request, "readiness_nonce": uuid.uuid4().hex}))
        self.assertIsNone(config.on_poll())
        self.assertTrue(workspace.read_control(config.control / "ack.json")["accepted"])
        self.assertTrue(self.state()["checkpoint_prepared"])
        self.assertNotEqual(self.state().get("checkpoint", {}).get("id"),
                            self.state()["activation_id"],
                            "Acknowledgement precedes cleanup/publication")

    def run_rollover(self):
        return self.call("start", "--wall-seconds", "100", "--primary-session-seconds", "30")

    def test_multiple_fresh_sessions_preserve_task_science_and_cumulative_resources(self):
        def changed_inputs(config, request, n):
            self.ack(config, request)
            if not n:
                (self.project / "starting_evidence/RESEARCH_QUESTIONS.md").write_text("Remove A; add C.")
                (self.project / "AGENTS.md").unlink()
                (self.project / "HUMAN_FEEDBACK.md").write_text("Check endpoint error.")
        with self.sessions(first=changed_inputs, count=2):
            code, out = self.run_rollover()
        self.assertEqual(code, 0, out)
        state = self.state()
        self.assertEqual(len(state["sessions"]), 3)
        self.assertEqual([s["outcome"] for s in state["sessions"]],
                         ["rolling_over", "rolling_over", "completed"])
        self.assertEqual(state["rollover"]["phase"], "continued")
        self.assertEqual(state["rollover"]["predecessor_native_session_id"], "native-1")
        self.assertEqual(state["rollover"]["successor_native_session_id"], "native-2")
        self.assertEqual(state["usage_totals"], {"input_tokens": 30, "output_tokens": 6})
        self.assertTrue(state["usage_complete"])
        self.assertEqual(state["active_seconds"], 41)
        self.assertEqual(state["remaining_active_seconds"], 59)
        self.assertEqual(sum(s["active_seconds"] for s in state["sessions"]), 41)
        self.assertEqual([s["predecessor_activation"] for s in state["sessions"]][1:],
                         [s["activation_id"] for s in state["sessions"]][:-1])
        self.assertEqual([s["service"] for s in state["sessions"]],
                         [context[0]["service"] for context in self.contexts])
        self.assertEqual([s["probe_service"] for s in state["sessions"]],
                         [context[0]["probe_service"] for context in self.contexts])
        self.assertEqual(len({s["probe_service"] for s in state["sessions"]}), 3)
        for session in state["sessions"]:
            self.assertTrue(session["cleanup_ok"])
            self.assertEqual(session["control_group"], f"/engineering/{session['service']}")
        prompt = self.contexts[1][2]
        for text in ("Remove A; add C.", "Check endpoint error.", "Use deterministic calculations.",
                     "AGENTS.md", "ADDED", "REMOVED"):
            self.assertIn(text, prompt)
        self.assertTrue(all(not p.exists() for p in self.auth_homes))
        self.assertFalse(state["accounting_pending"])

    def test_inter_session_intake_and_publication_time_charged_once(self):
        native_inputs, native_finalize = cli.continuation_inputs, workspace.finalize_science
        def inputs(*args):
            self.clock.return_value += 3
            return native_inputs(*args)
        def finalize(*args, **kwargs):
            result = native_finalize(*args, **kwargs)
            self.clock.return_value += 2
            return result
        with self.sessions(), patch.object(cli, "continuation_inputs", side_effect=inputs), \
             patch.object(workspace, "finalize_science", side_effect=finalize):
            code, out = self.run_rollover()
        self.assertEqual(code, 0, out)
        state = self.state()
        self.assertEqual(state["active_seconds"], 29)
        self.assertEqual(sum(s["active_seconds"] for s in state["sessions"]), 29)

    def test_missing_telemetry_stays_unknown_after_later_success(self):
        with self.sessions(usage=lambda n: n > 0, identities=lambda n: None if not n else "native-1"):
            code, out = self.run_rollover()
        self.assertEqual(code, 0, out)
        self.assertFalse(self.state()["usage_complete"])
        self.assertEqual(self.state()["usage_totals"], {"input_tokens": 10, "output_tokens": 2})
        self.assertIsNone(self.state()["sessions"][0]["native_session_id"])
        with self.sessions(identities=False):
            # Separate fresh project; absent identities remain explicitly unknown.
            self.project = self.project.parent / "unknown"
            (self.project / "starting_evidence").mkdir(parents=True)
            (self.project / "starting_evidence/RESEARCH_QUESTIONS.md").write_text("Compare rates.")
            code, out = self.run_rollover()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["rollover"]["phase"], "continued_identity_unknown")

    def test_failed_saving_never_continues_even_when_ordinary_handoff_can_publish(self):
        def ignored(config, request, n):
            pass
        with self.sessions(first=ignored):
            code, out = self.run_rollover()
        self.assertEqual(code, 4, out)
        self.assertEqual(len(self.contexts), 1)
        state = self.state()
        self.assertEqual(state["rollover"]["phase"], "failed")
        self.assertIn("not acknowledged", state["reason"])
        self.assertTrue(state["checkpoint"])
        with self.backend():
            self.assertEqual(self.call("resume")[0], 0)

    def test_changed_prepared_artifact_retains_previous_checkpoint(self):
        previous = self.start()["checkpoint"]
        def changed(config, request, n):
            self.ack(config, request)
            (config.drafts / "work/PLAN.md").write_text("# Unvalidated replacement")
        # Resume retains the policy, so persist the short policy as trusted test setup.
        state = self.state()
        state["primary_session_policy"]["session_seconds"] = 30
        state["limits"]["wall_seconds"] = 100
        self.save(state)
        with self.sessions(first=changed):
            code, out = self.call("resume")
        self.assertEqual(code, 4, out)
        self.assertEqual(self.state()["checkpoint"], previous)
        self.assertIn("Prepared artifact changed", self.state()["reason"])
        self.assertEqual(len(self.contexts), 1)

    def test_unconfirmed_cleanup_prevents_publication_and_successor(self):
        with self.sessions(cleanup=False):
            code, out = self.run_rollover()
        self.assertEqual(code, 4, out)
        self.assertFalse((self.project / "handoffs/primary.md").exists())
        self.assertEqual(len(self.contexts), 1)
        self.assertTrue(self.state()["accounting_pending"])
        self.assertEqual(self.state()["rollover"]["phase"], "failed")
        self.assertFalse(self.state()["sessions"][-1]["cleanup_ok"])

    def test_successor_startup_failure_retains_acknowledged_checkpoint(self):
        with self.sessions(startup_failure=True):
            code, out = self.run_rollover()
        self.assertEqual(code, 3, out)
        state = self.state()
        self.assertEqual(len(self.contexts), 1)
        self.assertEqual(len(state["sessions"]), 2)
        self.assertEqual(state["rollover"]["phase"], "failed")
        self.assertIsNone(state["sessions"][-1]["service"])
        self.assertIsNone(state["sessions"][-1]["probe_service"])
        self.assertIsNone(state["sessions"][-1]["control_group"])
        self.assertTrue(state["sessions"][-1]["cleanup_ok"])
        self.assertIn("Successor backend unavailable", state["rollover"]["limitation"])
        self.assertEqual(state["checkpoint"]["id"], state["sessions"][0]["activation_id"])
        self.assertTrue(state["cleanup_ok"])

    def test_reused_native_identity_is_error_and_cleanup_is_required(self):
        with self.sessions(identities=lambda n: "repeated"):
            code, out = self.run_rollover()
        self.assertEqual(code, 4, out)
        self.assertIn("reused a previous native session", self.state()["reason"])
        self.assertEqual(self.state()["rollover"]["phase"], "failed")
        self.assertTrue(self.state()["cleanup_ok"])

    def test_invalid_policy_rejected_before_creation_and_missing_policy_defaults(self):
        for value in ("0", "15", "nan", "inf", "-1"):
            with self.subTest(value=value), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.call("start", "--primary-session-seconds", value)
        self.assertFalse((self.project / ".research_pipeline").exists())
        self.start()
        state = self.state()
        launches = len(self.prompts)
        for policy in ([], {"mode": "tokens", "session_seconds": 30},
                       {"mode": "fixed_session_seconds", "session_seconds": "30"},
                       {"mode": "fixed_session_seconds", "session_seconds": 15}):
            state["primary_session_policy"] = policy
            self.save(state)
            with self.subTest(policy=policy), self.backend():
                self.assertEqual(self.call("resume")[0], 2)
                self.assertEqual(len(self.prompts), launches)
        state.pop("primary_session_policy")
        self.save(state)
        with self.backend():
            self.assertEqual(self.call("resume")[0], 0)
        self.assertEqual(self.state()["primary_session_policy"],
                         {"mode": "fixed_session_seconds", "session_seconds": 300})

    def test_investigation_deadline_does_not_request_unnecessary_rollover(self):
        def check(config):
            self.assertIsNone(config.on_poll.__self__.rollover_at)
            self.assertIsNone(config.on_poll())
            self.assertFalse((config.control / "request.json").exists())
        with self.backend(during=check):
            code, out = self.call("start", "--wall-seconds", "20", "--primary-session-seconds", "30")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.state()["sessions"]), 1)
        self.assertNotIn("rollover", self.state())

    def upgrade_to_pause(self, config, request):
        """A separate CLI follows foreground ownership and upgrades the request."""
        with patch.object(cli.time, "sleep", side_effect=RuntimeError("request persisted")):
            with self.assertRaisesRegex(RuntimeError, "request persisted"):
                cli.pause(self.project)
        upgraded = workspace.read_control(config.control / "request.json")
        self.assertEqual(upgraded, {**request, "reason": "pause"})
        return upgraded

    def test_pause_during_saving_rejects_stale_readiness_without_extending_grace(self):
        def pause(config, request, n):
            controller = config.on_poll.__self__
            deadline = controller.deadline
            self.clock.return_value += 3
            self.upgrade_to_pause(config, request)
            workspace.atomic_text(config.response / "ready.json",
                                  json.dumps({**request, "readiness_nonce": uuid.uuid4().hex}))
            self.assertIsNone(config.on_poll())
            self.assertIsNone(workspace.read_control(config.control / "ack.json"))
            self.assertEqual(controller.deadline, deadline)
            self.assertEqual(self.state()["state"], "pausing")
        with self.sessions(first=pause):
            code, out = self.run_rollover()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["state"], "paused")
        self.assertEqual(len(self.contexts), 1)
        self.assertEqual(self.state()["rollover"]["phase"], "paused")

    def test_accepted_rollover_checkpoint_remains_useful_when_pause_wins(self):
        def pause(config, request, n):
            self.ack(config, request)
            self.upgrade_to_pause(config, request)
        with self.sessions(first=pause):
            code, out = self.run_rollover()
        self.assertEqual(code, 0, out)
        state = self.state()
        self.assertEqual(state["state"], "paused")
        self.assertEqual(state["checkpoint"]["id"], state["activation_id"])
        self.assertEqual(len(self.contexts), 1)

    def test_pause_at_successor_registration_prevents_launch_and_charges_intake(self):
        native = cli.continuation_inputs
        def intake(project, state):
            result = native(project, state)
            self.clock.return_value += 4
            _, control, _ = workspace.control_paths(project, state)
            config = isolation.Config(control=control)
            self.upgrade_to_pause(config, workspace.read_control(control / "request.json"))
            return result
        with self.sessions(), patch.object(cli, "continuation_inputs", side_effect=intake):
            code, out = self.run_rollover()
        self.assertEqual(code, 0, out)
        state = self.state()
        self.assertEqual(state["state"], "paused")
        self.assertEqual(state["rollover"]["phase"], "paused")
        self.assertEqual(len(self.contexts), 1)
        self.assertEqual(state["active_seconds"], 23)
        self.assertEqual(state["sessions"][-1]["active_seconds"], 23)
        self.assertNotIn("recovery_finalization_pending", state)

    def test_pause_requester_follows_activation_changes_under_same_owner(self):
        self.start()
        original = self.state()
        calls = []
        def change_activation(_):
            state = self.state()
            calls.append(state["activation_id"])
            if len(calls) == 1:
                state["activation_id"] = uuid.uuid4().hex
                _, control, response = workspace.control_paths(self.project, state)
                control.mkdir(parents=True)
                response.mkdir()
                self.save(state)
            else:
                raise RuntimeError("second request persisted")
        with workspace.acquire_project_lock(self.project), \
             patch.object(cli.time, "sleep", side_effect=change_activation):
            with self.assertRaisesRegex(RuntimeError, "second request persisted"):
                cli.pause(self.project)
        self.assertEqual(self.state()["ownership_nonce"], original["ownership_nonce"])
        _, control, _ = workspace.control_paths(self.project, self.state())
        request = workspace.read_control(control / "request.json")
        self.assertEqual(request["activation_id"], self.state()["activation_id"])
        self.assertNotEqual(request["activation_id"], original["activation_id"])

    def test_exhaustion_during_publication_or_intake_blocks_successor(self):
        original = self.project
        for stage in ("publication", "intake"):
            self.project = original.parent / stage
            (self.project / "starting_evidence").mkdir(parents=True)
            (self.project / "starting_evidence/RESEARCH_QUESTIONS.md").write_text("Compare rates.")
            target = workspace if stage == "publication" else cli
            method = "finalize_science" if stage == "publication" else "continuation_inputs"
            native = getattr(target, method)
            def exhaust(*args, **kwargs):
                result = native(*args, **kwargs)
                self.clock.return_value = 1100
                return result
            with self.subTest(stage=stage), self.sessions(), patch.object(target, method, side_effect=exhaust):
                code, out = self.run_rollover()
            self.assertEqual(code, 124, out)
            self.assertEqual(self.state()["state"], "timed_out")
            self.assertEqual(self.state()["active_seconds"], 100)
            self.assertEqual(self.state()["remaining_active_seconds"], 0)
            self.assertEqual(len(self.contexts), 1)

    def test_handoff_human_conflict_blocks_rollover_and_preserves_edit(self):
        def edit(config, request, n):
            self.ack(config, request)
            (self.project / "handoffs/primary.md").write_text("# Human handoff correction")
        with self.sessions(first=edit):
            code, out = self.run_rollover()
        self.assertEqual(code, 4, out)
        state = self.state()
        self.assertEqual(state["state"], "failed")
        self.assertIn("conflicts with a human edit", state["reason"])
        self.assertEqual((self.project / "handoffs/primary.md").read_text(), "# Human handoff correction")
        self.assertEqual(state["pending_reconciliation"][0]["path"], "handoffs/primary.md")
        self.assertEqual(len(self.contexts), 1)

    def test_controller_killed_between_published_checkpoint_and_successor_recovers_once(self):
        root = self.project.parent / "crashed"
        (root / "starting_evidence").mkdir(parents=True)
        (root / "starting_evidence/RESEARCH_QUESTIONS.md").write_text("Compare rates.")
        script = r'''
import os, signal, sys
from pathlib import Path
from unittest.mock import patch
from research_pipeline import cli
from tests.test_rollover import RolloverTests
case = RolloverTests()
case.project = Path(sys.argv[1])
def crash(*args):
    assert case.state()["rollover"]["phase"] == "checkpointed"
    assert case.state()["cleanup_ok"]
    os.kill(os.getpid(), signal.SIGKILL)
with case.sessions(), patch.object(cli, "continuation_inputs", side_effect=crash):
    case.run_rollover()
'''
        process = subprocess.run([sys.executable, "-c", script, str(root)],
                                 capture_output=True, timeout=10)
        self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
        self.project = root
        saved = self.state()
        self.assertEqual(saved["rollover"]["phase"], "checkpointed")
        self.assertIn("recovery_finalization_pending", saved)
        # Match the subprocess controlled clock; recovery charges the gap once.
        with patch.object(cli.time, "monotonic", return_value=1023), \
             patch.object(isolation, "stop_service", return_value=True), \
             patch.object(isolation, "service_properties", return_value={}):
            cli.recover_owner(root, saved)
            recovered = self.state()
            self.assertEqual(recovered["active_seconds"], 23)
            self.assertEqual(recovered["rollover"]["phase"], "failed")
            self.assertEqual(recovered["checkpoint"], saved["checkpoint"])
            self.assertNotIn("recovery_finalization_pending", recovered)
            cli.recover_owner(root, recovered)
            self.assertEqual(self.state(), recovered)
        with self.backend():
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        self.assertIn("Controller lost", self.prompts[-1])


if __name__ == "__main__":
    unittest.main()
