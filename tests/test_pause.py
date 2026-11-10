"""Pause orchestration doubles. Production service cleanup lives in test_isolation."""
from contextlib import contextmanager
import json
import os
import signal
import subprocess
import sys
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from tests import use_checkout
from tests import test_continuity as fixtures

use_checkout()
from research_pipeline import cli, codex, isolation, workspace


class PauseTests(unittest.TestCase):
    setUp = fixtures.ContinuityTests.setUp
    call = fixtures.ContinuityTests.call
    state = fixtures.ContinuityTests.state
    save = fixtures.ContinuityTests.save
    backend = fixtures.ContinuityTests.backend
    start = fixtures.ContinuityTests.start

    def request(self, config, state=None):
        state = state or self.state()
        request = {"version": 1, **workspace.owner_fields(state), "reason": "pause",
                   "request_id": uuid.uuid4().hex, "requested_at": cli.now()}
        workspace.atomic_text(config.control / "request.json", json.dumps(request))
        return request

    def ready(self, config, request):
        ready = {**request, "readiness_nonce": uuid.uuid4().hex}
        workspace.atomic_text(config.response / "ready.json", json.dumps(ready))
        return ready

    def controller(self):
        state = self.state()
        session, control, response = workspace.control_paths(self.project, state)
        config = isolation.Config(deadline=time.monotonic() + 60, control=control,
                                  response=response, drafts=session / "drafts")
        baseline = workspace.science_fingerprints(self.project)
        return cli.CheckpointControl(self.project, state, config, workspace.read_intake(self.project),
                                session, baseline, [])

    def test_separate_pause_processes_handshake_before_cleanup_and_publication(self):
        callers = []
        request_ids = []
        def during(config):
            args = [sys.executable, "-m", "research_pipeline", "pause", str(self.project)]
            for _ in range(2):
                callers.append(subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            deadline = time.monotonic() + 5
            request = None
            while time.monotonic() < deadline:
                request = workspace.read_control(config.control / "request.json")
                if request:
                    break
                time.sleep(.02)
            self.assertIsNotNone(request, "Separate requester failed to create request")
            request_ids.append(request["request_id"])
            self.assertFalse((self.project / "work/PLAN.md").exists())
            self.ready(config, request)
            self.assertIsNone(config.on_poll())
            state = self.state()
            self.assertEqual(state["state"], "pausing")
            self.assertIn("checkpoint_prepared", state)
            self.assertTrue(workspace.read_control(config.control / "ack.json")["accepted"])
            self.assertFalse((self.project / "handoffs/primary.md").exists())
            self.assertTrue(all(p.poll() is None for p in callers),
                            "Requesters must wait for run.lock release and final accounting")
        try:
            with self.backend(during=during):
                code, out = self.call("start", "--wall-seconds", "60")
            self.assertEqual(code, 0, out)
            for process in callers:
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, stderr.decode())
                self.assertIn(b"suspension confirmed", stdout)
            state = self.state()
            self.assertEqual(state["state"], "paused")
            self.assertTrue(state["cleanup_ok"])
            self.assertEqual(state["sessions"][-1]["outcome"], "paused")
            self.assertFalse(state["accounting_pending"])
            self.assertEqual(state["checkpoint"]["id"], state["activation_id"])
            _, control, _ = workspace.control_paths(self.project, state)
            self.assertEqual(request_ids, [workspace.read_control(control / "request.json")["request_id"]])
            before = state["active_seconds"]
            with self.backend():
                self.assertEqual(self.call("resume")[0], 0)
            resumed = self.state()
            self.assertEqual(state["run_id"], resumed["run_id"])
            self.assertEqual(state["limits"], resumed["limits"])
            self.assertGreater(resumed["active_seconds"], before)
            self.assertNotEqual(state["native_session_id"], resumed["native_session_id"])
        finally:
            for process in callers:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    def test_pause_idle_and_stale_never_launches_and_preserves_limitations(self):
        state = self.start()
        state["checkpoint_error"] = "No new checkpoint saved."
        self.save(state)
        with patch.object(codex, "verify_backend", side_effect=AssertionError("inference")):
            code, out = self.call("pause")
            self.assertEqual(code, 0, out)
            self.assertIn("No new checkpoint", out)
            first = self.state()
            self.assertEqual(first["previous_outcome"], "completed")
            self.assertEqual(self.call("pause")[0], 0)
            self.assertEqual(self.state(), first)
            first.update(state="pausing", cleanup_ok=None, accounting_pending=True,
                         activation_started_epoch=time.time() - .2)
            self.save(first)
            with patch.object(isolation, "stop_service", return_value=True) as stop, \
                 patch.object(isolation, "service_properties", return_value={}):
                self.assertEqual(self.call("pause")[0], 0)
            stop.assert_called_once()
            self.assertEqual(self.state()["previous_outcome"], "interrupted")
            self.assertIn("Controller lost", self.state()["interrupted_work"])
            self.assertEqual(self.state()["checkpoint"], state["checkpoint"])

    def test_startup_and_preflight_requests_prevent_inference(self):
        self.start()
        for stage in ("startup", "preflight"):
            def stop(config, *args):
                self.request(config)
                if stage == "preflight":
                    self.assertEqual(config.on_poll(research=False), "pause")
                    raise isolation.RequestedStop("pause")
                return {}
            with self.subTest(stage=stage), \
                 patch.object(codex, "verify_backend", side_effect=stop if stage == "startup" else None,
                              return_value={}), \
                 patch.object(isolation, "preflight", side_effect=stop if stage == "preflight" else None), \
                 patch.object(isolation, "run_isolated") as launch, \
                 patch.object(codex, "private_auth") as auth:
                code, out = self.call("resume")
            self.assertEqual(code, 0, out)
            self.assertEqual(self.state()["state"], "paused")
            self.assertTrue(self.state()["cleanup_ok"])
            launch.assert_not_called()
            auth.assert_not_called()

    def test_grace_is_fixed_and_stale_or_malformed_readiness_cannot_extend_it(self):
        self.start()
        controller = self.controller()
        config = controller.config
        with patch.object(cli.time, "monotonic", return_value=100):
            request = self.request(config)
            config.deadline = 140
            self.assertIsNone(controller.poll())
            self.assertEqual(controller.deadline, 115)
        for kind in ("fifo", "symlink", "oversized", "malformed", "stale"):
            path = config.response / "ready.json"
            if path.exists() or path.is_symlink():
                path.unlink()
            if kind == "fifo":
                os.mkfifo(path)
            elif kind == "symlink":
                path.symlink_to(self.project / "starting_evidence/RESEARCH_QUESTIONS.md")
            elif kind == "oversized":
                path.write_text("x" * 9000)
            elif kind == "malformed":
                path.write_text("{")
            else:
                self.ready(config, {**request, "ownership_nonce": uuid.uuid4().hex})
            with patch.object(cli.time, "monotonic", return_value=114):
                self.assertIsNone(controller.poll())
                self.assertEqual(controller.deadline, 115)
        with patch.object(cli.time, "monotonic", return_value=115):
            self.assertEqual(controller.poll(), "pause")
        with patch.object(cli.time, "monotonic", return_value=116):
            self.assertEqual(controller.poll(), "pause")

    def test_rejected_handoff_can_be_corrected_without_extending_grace(self):
        self.start()
        controller = self.controller()
        request = self.request(controller.config)
        draft = controller.config.drafts / "handoffs/primary.md"
        original = draft.read_text()
        draft.write_text("# Missing fields")
        self.ready(controller.config, request)
        self.assertIsNone(controller.poll())
        self.assertFalse(workspace.read_control(controller.config.control / "ack.json")["accepted"])
        deadline = controller.deadline
        draft.write_text(original)
        self.ready(controller.config, request)
        self.assertIsNone(controller.poll())
        self.assertTrue(workspace.read_control(controller.config.control / "ack.json")["accepted"])
        self.assertEqual(controller.deadline, deadline)
        self.assertLessEqual(controller.ack_deadline, deadline)
        for link in ("../.research_pipeline/run.json", "../../outside.md"):
            with self.assertRaises(workspace.InputError):
                workspace.validate_handoff(self.project, original + f"\n[Bad]({link})")

    def test_slow_reference_hashing_abandons_preparation_at_saving_deadline(self):
        first = self.start()
        controller = self.controller()
        data = self.project / "work/data.csv"
        data.write_bytes(b"x" * 1024 * 1024)
        request = self.request(controller.config)
        self.ready(controller.config, request)
        native_open = type(data).open
        reads = []
        with patch.object(cli.time, "monotonic", return_value=100) as clock:
            controller.config.deadline = 140
            @contextmanager
            def slow_open(path, *args, **kwargs):
                with native_open(path, *args, **kwargs) as stream:
                    if path != data:
                        yield stream
                    else:
                        def read(size):
                            reads.append(size)
                            clock.return_value += 5
                            return stream.read(size)
                        yield SimpleNamespace(read=read)
            with patch.object(type(data), "open", slow_open):
                self.assertEqual(controller.poll(), "pause")
            self.assertEqual(clock.return_value, 115)
        self.assertEqual(reads, [64 * 1024] * 3, "Hashing must stop before reading the whole artifact")
        self.assertIsNone(controller.ack_deadline)
        self.assertIsNone(workspace.read_control(controller.config.control / "ack.json"))
        self.assertNotIn("checkpoint_prepared", controller.state)
        self.assertIn("saving deadline", controller.state["checkpoint_error"])
        self.assertEqual(self.state()["checkpoint"], first["checkpoint"])

    def prepared_controller(self):
        controller = self.controller()
        (controller.config.drafts / "work/PLAN.md").write_text("# Recovered scientific plan")
        self.ready(controller.config, self.request(controller.config))
        controller.poll()
        self.assertIn("checkpoint_prepared", self.state())
        return controller

    def test_recovery_retries_preparation_after_interruption_at_cleanup_state_write(self):
        self.start()
        self.prepared_controller()
        native_write = workspace.write_state
        def interrupt(project, state):
            native_write(project, state)
            if state["state"] == "interrupted" and state["cleanup_ok"]:
                raise KeyboardInterrupt
        with workspace.acquire_project_lock(self.project), \
             patch.object(isolation, "stop_service", return_value=True), \
             patch.object(isolation, "service_properties", return_value={}), \
             patch.object(workspace, "write_state", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                cli.recover_owner(self.project, self.state())
        saved = self.state()
        self.assertEqual(saved["state"], "interrupted")
        self.assertTrue(saved["cleanup_ok"])
        self.assertFalse(saved["accounting_pending"])
        self.assertIn("checkpoint_prepared", saved)
        with workspace.acquire_project_lock(self.project), \
             patch.object(isolation, "stop_service") as stop:
            cli.recover_owner(self.project, saved)
        stop.assert_not_called()
        self.assertNotIn("checkpoint_prepared", self.state())
        self.assertEqual((self.project / "work/PLAN.md").read_text(), "# Recovered scientific plan")
        self.assertNotIn("checkpoint_error", self.state())

    def test_recovery_finalization_charges_validation_and_publication_once_with_cap(self):
        self.start()
        for remaining in (20, 3):
            with self.subTest(remaining=remaining):
                self.prepared_controller()
                state = self.state()
                state["state"] = "interrupted"  # Service cleanup/accounting already persisted.
                state["active_seconds"] = state["limits"]["wall_seconds"] - remaining
                state["sessions"][-1]["active_seconds"] = state["active_seconds"]
                before = state["active_seconds"]
                previous_recovery = state.get("recovery_finalization_seconds", 0)
                usage = state["usage_totals"].copy()
                load, finalize = workspace.load_prepared, workspace.finalize_science
                with patch.object(cli.time, "monotonic", return_value=100) as clock:
                    def validate(*args):
                        result = load(*args)
                        clock.return_value += 2
                        return result
                    def publish(*args, **kwargs):
                        result = finalize(*args, **kwargs)
                        clock.return_value += 3
                        return result
                    with workspace.acquire_project_lock(self.project), \
                         patch.object(isolation, "stop_service", return_value=True), \
                         patch.object(isolation, "service_properties", return_value={}), \
                         patch.object(workspace, "load_prepared", side_effect=validate), \
                         patch.object(workspace, "finalize_science", side_effect=publish):
                        cli.recover_owner(self.project, state)
                    recovered = self.state()
                    charged = min(5, remaining)
                    self.assertEqual(recovered["active_seconds"], before + charged)
                    self.assertEqual(recovered["remaining_active_seconds"], remaining - charged)
                    self.assertEqual(recovered["recovery_finalization_seconds"], previous_recovery + charged)
                    self.assertEqual(recovered["sessions"][-1]["active_seconds"], before + charged)
                    self.assertEqual(recovered["usage_totals"], usage)
                    self.assertNotIn("recovery_finalization_pending", recovered)
                    clock.return_value = 200
                    with workspace.acquire_project_lock(self.project):
                        cli.recover_owner(self.project, recovered)
                    self.assertEqual(self.state(), recovered, "Repeated recovery must not charge saved intervals twice")

    def test_interrupted_recovery_accounting_is_settled_once_before_retry(self):
        first = self.start()
        self.prepared_controller()
        native_write = workspace.write_state
        def interrupt(project, state):
            native_write(project, state)
            if state.get("recovery_finalization_pending"):
                raise KeyboardInterrupt
        with patch.object(cli.time, "monotonic", return_value=100) as clock:
            with workspace.acquire_project_lock(self.project), \
                 patch.object(isolation, "stop_service", return_value=True), \
                 patch.object(isolation, "service_properties", return_value={}), \
                 patch.object(workspace, "write_state", side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    cli.recover_owner(self.project, self.state())
            saved = self.state()
            self.assertIn("checkpoint_prepared", saved)
            self.assertIn("recovery_finalization_pending", saved)
            clock.return_value = 104
            with workspace.acquire_project_lock(self.project):
                cli.recover_owner(self.project, saved)
            recovered = self.state()
            self.assertAlmostEqual(recovered["active_seconds"], first["active_seconds"] + 4)
            self.assertEqual(recovered["recovery_finalization_seconds"], 4)
            self.assertNotIn("recovery_finalization_pending", recovered)
            self.assertIn("Interrupted recovery finalization", recovered["accounting_uncertainties"][-1])
            clock.return_value = 200
            with workspace.acquire_project_lock(self.project):
                cli.recover_owner(self.project, recovered)
            self.assertEqual(self.state(), recovered)

    def test_cleanup_failure_blocks_pause_publication_and_resume(self):
        first = self.start()
        before = (self.project / "work/PLAN.md").read_text()
        def during(config):
            self.request(config)
            config.on_poll()
            (config.drafts / "work/PLAN.md").write_text("# Must remain private")
        with self.backend(during=during, cleanup=False):
            code, out = self.call("resume")
        self.assertEqual(code, 4, out)
        self.assertEqual(self.state()["state"], "failed")
        self.assertTrue(self.state()["accounting_pending"])
        self.assertEqual(self.state()["checkpoint"], first["checkpoint"])
        self.assertEqual((self.project / "work/PLAN.md").read_text(), before)
        with patch.object(isolation, "stop_service", return_value=False):
            self.assertEqual(self.call("pause")[0], 2)
            self.assertEqual(self.call("resume")[0], 2)

    def test_forced_pause_invalid_drafts_still_reports_suspension(self):
        first = self.start()
        def during(config):
            self.request(config)
            config.on_poll()
        with self.backend(during=during, bad_draft=True):
            code, out = self.call("resume")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["state"], "paused")
        self.assertIn("Checkpoint finalization failed", self.state()["checkpoint_error"])
        self.assertEqual(self.state()["checkpoint"], first["checkpoint"])

    def test_crash_after_preparation_recovers_guarded_publication(self):
        first = self.start()
        script = r'''
from contextlib import contextmanager
import json, os, signal, sys, uuid
from unittest.mock import patch
from research_pipeline import cli, codex, isolation, workspace
@contextmanager
def auth(project):
    yield project / ".research_pipeline"
def crash(config, project, argv, prompt, recorder, auth):
    state = cli.load_state(project)
    request = {"version": 1, **workspace.owner_fields(state), "reason": "pause",
               "request_id": uuid.uuid4().hex, "requested_at": cli.now()}
    for name in ("work", "handoffs"):
        (config.drafts / name).mkdir()
    (config.drafts / "work/PLAN.md").write_text("# Newly prepared plan")
    (config.drafts / "handoffs/primary.md").write_text((project / "handoffs/primary.md").read_text())
    workspace.atomic_text(config.control / "request.json", json.dumps(request))
    workspace.atomic_text(config.response / "ready.json",
                          json.dumps({**request, "readiness_nonce": uuid.uuid4().hex}))
    recorder("stdout", b'{"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":2}}\n')
    config.on_poll()
    assert workspace.read_control(config.control / "ack.json")["accepted"]
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
        prepared = self.state()
        self.assertEqual(prepared["state"], "pausing")
        self.assertIn("checkpoint_prepared", prepared)
        # Human edits made during saving win even on recovery.
        (self.project / "work/PLAN.md").write_text("# Human correction after preparation")
        with patch.object(isolation, "stop_service", return_value=True), \
             patch.object(isolation, "service_properties", return_value={}):
            code, out = self.call("pause")
        self.assertEqual(code, 0, out)
        recovered = self.state()
        self.assertTrue(recovered["cleanup_ok"])
        self.assertEqual((self.project / "work/PLAN.md").read_text(), "# Human correction after preparation")
        self.assertEqual(recovered["pending_reconciliation"][0]["path"], "work/PLAN.md")
        self.assertNotIn("checkpoint_prepared", recovered)
        self.assertNotEqual(recovered["checkpoint"]["id"], first["checkpoint"]["id"])
        self.assertEqual(recovered["run_id"], first["run_id"])
        self.assertEqual(recovered["usage_totals"]["input_tokens"], first["usage_totals"]["input_tokens"] + 7)
        self.assertGreaterEqual(recovered["active_seconds"], first["active_seconds"])

    def test_damaged_preparation_retains_checkpoint_after_cleanup(self):
        first = self.start()
        controller = self.controller()
        request = self.request(controller.config)
        self.ready(controller.config, request)
        controller.poll()
        os.mkfifo(controller.config.drafts / "invalid.md")
        with patch.object(isolation, "stop_service", return_value=True) as stop, \
             patch.object(isolation, "service_properties", return_value={}):
            code, out = self.call("pause")
        self.assertEqual(code, 0, out)
        stop.assert_called_once()
        self.assertEqual(self.state()["checkpoint"], first["checkpoint"])
        self.assertIn("Interrupted checkpoint finalization", self.state()["checkpoint_error"])

    def test_pause_timeout_leaves_request_pending_and_replacement_conflicts(self):
        self.start()
        # The helper is tested under a held lock; no owner consumes the request.
        with workspace.acquire_project_lock(self.project), patch.object(cli, "PAUSE_TIMEOUT", .05):
            code, out = self.call("pause")
        self.assertEqual(code, 2, out)
        self.assertIn("not confirmed", out)
        controller = self.controller()
        self.assertIsNotNone(controller.current_request())
        request = controller.current_request()
        controller.state["ownership_nonce"] = uuid.uuid4().hex
        self.assertIsNone(controller.current_request(), "Stale request must not affect another owner")
        self.assertFalse(workspace.matching_request(request, controller.state))
        # A requester must report replacement rather than following the new owner.
        def replace_owner(_):
            state = self.state()
            state["ownership_nonce"] = uuid.uuid4().hex
            self.save(state)
        with workspace.acquire_project_lock(self.project), \
             patch.object(cli.time, "sleep", side_effect=replace_owner):
            code, out = self.call("pause")
        self.assertEqual(code, 2, out)
        self.assertIn("ownership conflict", out)

    def test_launch_guard_serializes_request_check_with_spawn(self):
        self.start()
        controller = self.controller()
        self.request(controller.config)
        with patch.object(isolation.subprocess, "Popen") as spawn, \
             patch.object(isolation, "stop_service", return_value=True), \
             patch.object(isolation, "service_properties", return_value={}):
            result = isolation.run_isolated(controller.config, self.project,
                ["/usr/bin/true"], launch_guard=controller.launch_guard)
        spawn.assert_not_called()
        self.assertEqual(result.requested_stop, "pause")
        self.assertTrue(result.cleanup_ok)

    def test_launcher_polls_after_worker_closes_both_streams(self):
        """Local pipe fixture doubles the service; proves polling after pipe EOF."""
        self.start()
        began = time.monotonic()
        config = isolation.Config(deadline=began + 3)
        native_popen = subprocess.Popen
        def spawn(command, **kwargs):
            return native_popen([sys.executable, "-c",
                                 "import os,time; os.close(1); os.close(2); time.sleep(20)"], **kwargs)
        with patch.object(isolation.subprocess, "Popen", side_effect=spawn), \
             patch.object(isolation, "stop_service", return_value=True), \
             patch.object(isolation, "service_properties", return_value={}):
            result = isolation.run_isolated(config, self.project, ["/usr/bin/true"],
                poll=lambda: "pause" if time.monotonic() - began >= .4 else None)
        self.assertEqual(result.requested_stop, "pause")
        self.assertFalse(result.timed_out)
        self.assertLess(time.monotonic() - began, 2)


if __name__ == "__main__":
    unittest.main()
