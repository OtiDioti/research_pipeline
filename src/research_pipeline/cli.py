"""Foreground investigation activations with checkpoint-based continuation."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

from . import codex, isolation, workspace

SAVING_GRACE = 15
PAUSE_TIMEOUT = 60
ACK_EXIT_GRACE = 1


class CheckpointControl:
    """One ownership-scoped request; duplicate readiness never extends grace."""
    def __init__(self, project, state, config, intake, session, baseline, external):
        self.project, self.state, self.config = project, state, config
        self.intake, self.session = intake, session
        self.baseline, self.external = baseline, external
        self.request = None
        self.deadline = None
        self.ack_deadline = None
        self.last_readiness = None
        self.rollover_at = None

    def current_request(self):
        request = workspace.read_control(self.config.control / "request.json")
        return request if workspace.matching_request(request, self.state) else None

    @contextmanager
    def launch_guard(self):
        with workspace.control_lock(self.project):
            request = self.current_request()
            if request:
                raise isolation.RequestedStop(request["reason"])
            yield

    def poll(self, research=True):
        if research and self.rollover_at is not None and time.monotonic() >= self.rollover_at:
            with workspace.control_lock(self.project):
                if not self.current_request():
                    request = {"version": 1, **workspace.owner_fields(self.state),
                               "request_id": uuid.uuid4().hex, "reason": "rollover",
                               "requested_at": now()}
                    workspace.atomic_text(self.config.control / "request.json", json.dumps(request) + "\n")
        request = self.current_request()
        if not request:
            return None
        if self.request is None:
            self.request = request
            self.deadline = min(self.config.deadline, time.monotonic() + SAVING_GRACE)
        self.request = request
        reason = request["reason"]
        if self.state["state"] != ("pausing" if reason == "pause" else "rolling_over"):
            self.state.update(state="pausing" if reason == "pause" else "rolling_over",
                              reason=f"Saving progress for {reason}.",
                              pause_request_id=request["request_id"])
            if reason == "rollover":
                self.state["rollover"] = {
                    "source_activation": self.state["activation_id"],
                    "request_id": request["request_id"], "phase": "saving",
                    "saving_deadline_monotonic": self.deadline,
                    "predecessor_native_session_id": self.state.get("native_session_id")}
            workspace.write_state(self.project, self.state)
        if not research:
            return reason
        if time.monotonic() >= (self.ack_deadline or self.deadline):
            return reason
        ready = workspace.read_control(self.config.response / "ready.json")
        nonce = ready.get("readiness_nonce") if ready else None
        if (ready and all(ready.get(k) == v for k, v in request.items())
                and isinstance(nonce, str) and re.fullmatch(r"[a-f0-9]{32}", nonce)
                and nonce != self.last_readiness and self.ack_deadline is None):
            self.last_readiness = nonce
            ack = {**ready, "accepted": False}
            try:
                workspace.prepare_checkpoint(self.project, self.state, self.intake,
                    self.session, self.config.drafts, self.baseline, self.external,
                    deadline=self.deadline)
                workspace.check_deadline(self.deadline)
                ack["accepted"] = True
                self.ack_deadline = min(self.deadline, time.monotonic() + ACK_EXIT_GRACE)
            except TimeoutError as exc:
                self.state["checkpoint_error"] = str(exc)
                return reason
            except (OSError, ValueError, UnicodeError) as exc:
                ack["error"] = str(exc)[:1000]
            workspace.atomic_text(self.config.control / "ack.json", json.dumps(ack) + "\n")
        return None


def pause(project):
    """Request live suspension, or recover an idle/stale owner under run.lock."""
    project = validate_project(project)
    # Do not create an investigation as a side effect of an invalid pause.
    load_state(project)
    deadline = time.monotonic() + PAUSE_TIMEOUT
    target = None
    while time.monotonic() < deadline:
        try:
            with workspace.acquire_project_lock(project):
                state = load_state(project)
                if target and foreground_owner(state) != target:
                    raise workspace.InputError("Pause ownership conflict: another activation replaced the target")
                recover_owner(project, state)
                if state.get("cleanup_ok") is not True:
                    raise workspace.InputError("Suspension cleanup is unconfirmed")
                if state["state"] != "paused":
                    state["previous_outcome"] = state["state"]
                    state.update(state="paused", reason="Full suspension confirmed; no research work remains.")
                with workspace.control_lock(project):
                    workspace.write_state(project, state)
                limitation = state.get("checkpoint_error") or (
                    "Using the latest saved checkpoint." if state.get("checkpoint")
                    else "No valid checkpoint; only ordinary artifacts are available.")
                print(f"paused: full service/descendant suspension confirmed. {limitation}")
                return 0
        except workspace.ProjectBusy:
            pass
        with workspace.control_lock(project):
            state = load_state(project)
            owner = workspace.owner_fields(state)
            if target and target != foreground_owner(state):
                raise workspace.InputError("Pause ownership conflict: another activation replaced the target")
            target = foreground_owner(state)
            _, control, _ = workspace.control_paths(project, state)
            request = workspace.read_control(control / "request.json")
            if not workspace.matching_request(request, state):
                request = {"version": 1, **owner, "request_id": uuid.uuid4().hex,
                           "reason": "pause", "requested_at": now()}
                workspace.atomic_text(control / "request.json", json.dumps(request) + "\n")
            elif request["reason"] == "rollover":
                request["reason"] = "pause"
                workspace.atomic_text(control / "request.json", json.dumps(request) + "\n")
        time.sleep(.1)
    raise workspace.InputError("Pause confirmation timed out; request remains pending; suspension is not confirmed")


def foreground_owner(state):
    owner = workspace.owner_fields(state)
    return owner["run_id"], owner["ownership_nonce"]


def session_seconds(value):
    number = positive(value)
    if number <= SAVING_GRACE:
        raise argparse.ArgumentTypeError(f"must exceed the {SAVING_GRACE}-second saving grace")
    return number


def positive(value):
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive finite number") from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


def positive_int(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def now():
    return datetime.now(timezone.utc).isoformat()


def boot_identity():
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None


def inspect_project(project):
    project = Path(os.path.abspath(project))
    try:
        state = json.loads((project / ".research_pipeline/run.json").read_text())
    except (OSError, ValueError) as exc:
        raise workspace.InputError(f"No readable investigation state: {exc}") from exc
    state["artifact_availability"] = {
        p: (project / p).is_file() and not (project / p).is_symlink()
        for p in state.get("artifacts", [])
    }
    state["activity_check"] = ("Cleanup unconfirmed; residual work may still be active."
                               if state.get("cleanup_ok") is False else
                               "Terminal state recorded; no live session requested.")
    if state.get("state") in workspace.ACTIVE_STATES:
        held = False
        try:
            with (project / ".research_pipeline/run.lock").open() as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    held = True
        except OSError:
            pass
        state["activity_check"] = ("Controller lock held; live service status unconfirmed."
                                   if held else "Stale activity: controller lock is not held; run may have crashed.")
        if held and state.get("service"):
            try:
                props = isolation.service_properties(state["service"])
                state["activity_check"] += f" Service ActiveState={props.get('ActiveState', 'unknown')}."
            except (isolation.RuntimeUnavailable, OSError, subprocess.TimeoutExpired):
                pass
    return state


def validate_project(project):
    project = Path(os.path.abspath(project))
    if not project.is_dir() or any(p.is_symlink() for p in (project, *project.parents)):
        raise workspace.InputError("Project must be an existing directory with no symlink ancestors")
    return project


def load_state(project):
    # Drafts are untrusted and may belong to a still-live orphan. Read only the
    # trusted state needed to stop it; validate other operational paths afterward.
    path = workspace.safe_path(project, ".research_pipeline/run.json")
    if not path.is_file():
        raise workspace.InputError("Investigation state must be a regular file")
    state = json.loads(path.read_text())
    if state.get("schema_version") != 2:
        raise workspace.InputError("Unsupported state schema; M1 projects are inspectable but cannot resume")
    if state.get("project") != str(project) or state.get("logical_researcher_id") != "primary":
        raise workspace.InputError("Saved project/logical identity is invalid")
    for key in ("service", "probe_service"):
        attempted = state.get("service_attempted" if key == "service" else "probe_attempted")
        if attempted and not state.get(key):
            raise workspace.InputError(f"Missing saved {key} for attempted launch")
        if state.get(key) and not re.fullmatch(r"research-[a-f0-9]{32}\.service", state[key]):
            raise workspace.InputError(f"Invalid saved {key}")
    limits = state["limits"]
    if (positive(str(limits["wall_seconds"])) != limits["wall_seconds"]
            or positive_int(str(limits["memory_mib"])) != limits["memory_mib"]
            or positive_int(str(limits["max_tasks"])) != limits["max_tasks"]):
        raise workspace.InputError("Invalid saved limits")
    consumed = state.get("active_seconds", 0)
    if not isinstance(consumed, (int, float)) or not math.isfinite(consumed) or consumed < 0:
        raise workspace.InputError("Invalid saved active-work accounting")
    policy = state.setdefault("primary_session_policy",
                              {"mode": "fixed_session_seconds", "session_seconds": 300})
    if not isinstance(policy, dict) or policy.get("mode") != "fixed_session_seconds":
        raise workspace.InputError("Invalid saved primary-session policy")
    if session_seconds(str(policy["session_seconds"])) != policy["session_seconds"]:
        raise workspace.InputError("Invalid saved primary-session duration")
    return state


def finish_recovery_accounting(state, interrupted=False):
    """Settle one saved finalization interval together with its pending marker."""
    interval = state.pop("recovery_finalization_pending")
    same_clock = (not interrupted or interval["boot_id"] is not None
                  and interval["boot_id"] == boot_identity())
    elapsed = (time.monotonic() - interval["started_monotonic"] if same_clock
               else time.time() - interval["started_epoch"])
    remaining = max(0, state["limits"]["wall_seconds"] - state.get("active_seconds", 0))
    charged = min(remaining, interval["allowance"], max(0, elapsed))
    state["active_seconds"] = state.get("active_seconds", 0) + charged
    state["remaining_active_seconds"] = remaining - charged
    state["recovery_finalization_seconds"] = state.get("recovery_finalization_seconds", 0) + charged
    for session in state.get("sessions", []):
        if session["activation_id"] == state["activation_id"]:
            session["active_seconds"] = session.get("active_seconds", 0) + charged
            session["recovery_finalization_seconds"] = session.get("recovery_finalization_seconds", 0) + charged
    if interrupted:
        state.setdefault("accounting_uncertainties", []).append(
            "Interrupted recovery finalization: conservatively charged elapsed time through recovery, "
            "capped at its remaining allowance; the exact lost-controller work interval is unknown.")


def recover_owner(project, state):
    """Called under the exclusive lock before reading agent-mutated science."""
    unresolved = state.get("state") in workspace.ACTIVE_STATES or state.get("cleanup_ok") is False
    service_ends = []
    for key in ("probe_service", "service"):
        attempted = state.get("probe_attempted" if key == "probe_service" else "service_attempted")
        if attempted and (unresolved or state.get("cleanup_ok") is not True):
            if not isolation.stop_service(state[key]):
                state.update(state="failed", cleanup_ok=False,
                             reason="Previous service/descendant cleanup could not be confirmed; launch blocked.")
                workspace.write_state(project, state)
                raise workspace.InputError(state["reason"])
            try:
                props = isolation.service_properties(state[key])
                service_ends.append(int(props.get("InactiveEnterTimestampMonotonic", 0)) / 1e6)
            except (OSError, ValueError, isolation.RuntimeUnavailable, subprocess.TimeoutExpired):
                service_ends.append(0)
    if unresolved or state.get("accounting_pending"):
        if state.get("accounting_pending"):
            # A dead controller has no trustworthy monotonic interval. Charge
            # elapsed real time, capped at its recorded allocation/deadline.
            elapsed = max(0, time.time() - state["activation_started_epoch"])
            measured = (bool(service_ends) and all(service_ends)
                        and state.get("boot_id") is not None and state["boot_id"] == boot_identity()
                        and max(service_ends) >= state.get("activation_started_monotonic", math.inf))
            if measured:
                elapsed = max(service_ends) - state["activation_started_monotonic"]
            previously_charged = state.get("activation_charged_seconds", 0)
            charged = max(previously_charged, min(state["activation_allowance"], elapsed))
            state["active_seconds"] = min(state["limits"]["wall_seconds"],
                                           state.get("active_seconds", 0) + (charged - previously_charged))
            state["activation_charged_seconds"] = charged
            state["remaining_active_seconds"] = max(0, state["limits"]["wall_seconds"] - state["active_seconds"])
            state["accounting_pending"] = False
            state.setdefault("accounting_uncertainties", []).append(
                ("Lost controller: charged startup through observed service inactivity, bounded by its allocation; "
                 if measured else
                 "Lost controller: charged elapsed wall time up to the original activation deadline; "
                 "no reliable service active interval was available. ")
                + "Unobserved model usage and interrupted finalization remain unknown.")
            state["usage_complete"] = False
        state.update(state="interrupted", cleanup_ok=True,
                     interrupted_work="Controller lost; work after the last valid checkpoint may be incomplete. "
                     "Inspect retained artifacts before repeating computations.",
                     reason="Stale ownership recovered after confirmed service cleanup.")
        if state.get("rollover", {}).get("phase") in ("saving", "checkpointed", "starting"):
            state["rollover"].update(phase="failed",
                limitation="Controller lost during rollover; explicit resume uses valid saved science.")
        if not any(s["activation_id"] == state.get("activation_id") for s in state.setdefault("sessions", [])):
            state["sessions"].append({
                "activation_id": state.get("activation_id"), "native_session_id": state.get("native_session_id"),
                "outcome": "interrupted", "usage_totals": state.get("current_usage_totals")})
        for session in state["sessions"]:
            if session["activation_id"] == state.get("activation_id"):
                session["active_seconds"] = state.get("activation_charged_seconds", 0)
        workspace.write_state(project, state)
    # Cleanup/accounting can already be durable when an earlier recovery dies.
    # Pending preparation must remain independently recoverable in that state.
    if state.get("cleanup_ok") is True:
        if state.get("recovery_finalization_pending"):
            finish_recovery_accounting(state, interrupted=True)
            workspace.write_state(project, state)
        if state.get("checkpoint_prepared"):
            remaining = max(0, state["limits"]["wall_seconds"] - state.get("active_seconds", 0))
            state["recovery_finalization_pending"] = {
                "started_monotonic": time.monotonic(), "started_epoch": time.time(),
                "boot_id": boot_identity(), "allowance": remaining,
            }
            workspace.write_state(project, state)
            try:
                try:
                    prepared, session, intake, accepted = workspace.load_prepared(project, state)
                    workspace.finalize_science(project, state, intake, session, session / "drafts",
                        prepared["baseline"], prepared["external_changes"],
                        expected=state.get("science_fingerprints"), accepted_intake=accepted)
                except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
                    state["checkpoint_error"] = f"Interrupted checkpoint finalization: {exc}; previous checkpoint retained"
                state.pop("checkpoint_prepared", None)
            finally:
                finish_recovery_accounting(state)
                workspace.write_state(project, state)


def start(project, config):
    return activate(project, config, resume=False)


def resume(project, codex_path="codex", model=None):
    return activate(project, isolation.Config(codex=codex_path, model=model), resume=True)


def continuation_inputs(project, state):
    intake = workspace.read_intake(project)
    saved, handoff, historical = workspace.load_checkpoint(project, state)
    state["recovery"] = {
        "checkpoint_id": saved["id"] if saved else None,
        "limitation": ("No valid checkpoint; continue from retained ordinary artifacts."
                       if not saved else
                       "Newest checkpoint invalid; using the previous saved handoff."
                       if saved["id"] != state.get("checkpoint", {}).get("id") else None),
    }
    baseline = workspace.science_fingerprints(project)
    external = sorted(set(workspace.changed_files(state.get("science_fingerprints", {}), baseline))
                      | set(state.get("pending_human_changes", [])))
    continuation = {
        "investigation_id": state["run_id"], "logical_researcher_id": "primary",
        "checkpoint_id": saved["id"] if saved else None,
        "recovery": state["recovery"],
        "handoff": handoff or "No valid saved checkpoint; continue cautiously from ordinary artifacts.",
        "previous_accepted_intake": historical or "(no accepted intake)",
        "input_changes": workspace.changed_files(
            saved["input_fingerprints"] if saved else state.get("input_fingerprints", {}),
            intake.fingerprints),
        "external_markdown_changes_or_deletions": external,
        "pending_reconciliation": state.get("pending_reconciliation", []),
        "interrupted_work": state.get("interrupted_work"),
        "missing_saved_artifacts": [rel for rel in saved["artifacts"]
                                     if not workspace.safe_path(project, rel).is_file()] if saved else [],
    }
    return intake, baseline, external, continuation


def activate(project, config, resume=False):
    session_seconds(str(config.primary_session_seconds))
    project = validate_project(project)
    with workspace.acquire_project_lock(project):
        began = time.monotonic()
        continuation = None
        if resume:
            state = load_state(project)
            recover_owner(project, state)
            began = time.monotonic()
            for key in ("wall_seconds", "memory_mib", "max_tasks"):
                setattr(config, key, state["limits"][key])
            config.primary_session_seconds = state["primary_session_policy"]["session_seconds"]
            remaining = max(0, config.wall_seconds - state.get("active_seconds", 0))
            if remaining <= 0:
                raise workspace.InputError("Investigation active-work allowance exhausted; resume cannot increase limits")
            intake, baseline, external, continuation = continuation_inputs(project, state)
        else:
            workspace.validate_fresh(project)
            intake = workspace.read_intake(project)
            remaining = config.wall_seconds
            state = {"schema_version": 2, "run_id": uuid.uuid4().hex, "project": str(project),
                     "logical_researcher_id": "primary", "started_at": now(),
                     "limits": config.limits(), "capabilities": {}, "backend": {},
                     "primary_session_policy": {"mode": "fixed_session_seconds",
                                                "session_seconds": config.primary_session_seconds},
                     "artifacts": list(workspace.REQUIRED), "checkpoints": [], "sessions": [],
                     "active_seconds": 0, "usage_totals": None, "usage_complete": True,
                     "limitations": codex.LIMITATIONS, "pending_reconciliation": []}
            for name in workspace.MANAGED:
                (project / name).mkdir()
            workspace.initial_status(project)
            workspace.refresh_indexes(project)
            baseline = workspace.science_fingerprints(project)
            external = []
        investigation_deadline = began + remaining
        state["ownership_nonce"] = uuid.uuid4().hex
        previous = None
        while True:
            code, controller, ended = run_session(project, config, state, intake, baseline,
                                                  external, continuation, began,
                                                  investigation_deadline, previous)
            if state["state"] != "rolling_over" or state.get("rollover", {}).get("phase") != "checkpointed":
                break
            # Keep the stopped predecessor registered while reloading human inputs.
            # Its pending interval covers a crash during this preparation.
            began = ended
            try:
                intake, baseline, external, continuation = continuation_inputs(project, state)
            except (OSError, ValueError, UnicodeError) as exc:
                state.update(state="failed", reason=f"Rollover continuation intake failed: {exc}")
                state["rollover"].update(phase="failed", limitation=state["reason"])
                finish_recovery_accounting(state)
                workspace.write_state(project, state)
                code = 4
                break
            previous = controller
        print(f"{state['state']}: {state['reason']}\nStatus: {project / 'RESEARCH_STATUS.md'}")
        return code


def run_session(project, config, state, intake, baseline, external, continuation,
                began, investigation_deadline, previous):
    """One fresh backend context; caller retains run.lock across all sessions."""
    remaining = max(0, config.wall_seconds - state.get("active_seconds", 0))
    predecessor = state.get("activation_id") if previous else None
    config.deadline = investigation_deadline
    with workspace.control_lock(project):
        if previous:
            request = previous.current_request()
            if request and request["reason"] == "pause":
                state.update(state="paused", reason="Full suspension confirmed before successor registration.")
                state["rollover"].update(phase="paused", limitation="Human pause prevented continuation.")
                finish_recovery_accounting(state)
                state["sessions"][-1]["outcome"] = "paused"
                workspace.write_state(project, state)
                return 0, previous, time.monotonic()
            if time.monotonic() >= investigation_deadline:
                state.update(state="timed_out", reason="Active-work allowance exhausted before continuation.")
                state["rollover"].update(phase="exhausted")
                finish_recovery_accounting(state)
                workspace.write_state(project, state)
                return 124, previous, time.monotonic()
        config.unit = f"research-{uuid.uuid4().hex}.service"
        activation = uuid.uuid4().hex
        session = project / ".research_pipeline/sessions" / activation
        session.mkdir(parents=True)
        config.drafts = session / "drafts"
        config.drafts.mkdir()
        began_epoch = time.time() - max(0, time.monotonic() - began)
        for key in ("execution", "telemetry"):
            state.pop(key, None)
        state["limitations"] = codex.LIMITATIONS
        state.update(activation_id=activation,
                     native_session_id=None, service=config.unit, service_attempted=False,
                     probe_service=None, probe_attempted=False, cleanup_ok=None,
                     state="starting", reason="Checking runtime prerequisites.",
                     activation_started_epoch=began_epoch, activation_allowance=remaining,
                     activation_started_monotonic=began, boot_id=boot_identity(),
                     activation_deadline_epoch=began_epoch + remaining,
                     accounting_pending=True, activation_charged_seconds=0, remaining_active_seconds=remaining,
                     input_fingerprints=intake.fingerprints, input_inventory=intake.inventory,
                     validation_failures=[], external_changes=external,
                     pending_intake_changes=False, current_usage_totals=None)
        _, config.control, config.response = workspace.control_paths(project, state)
        config.control.mkdir()
        config.response.mkdir()
        state.pop("checkpoint_prepared", None)
        state.pop("pause_request_id", None)
        if previous:
            state.pop("recovery_finalization_pending", None)
            state["rollover"].update(phase="starting", destination_activation=activation)
            state["sessions"][-1]["successor_activation"] = activation
        workspace.write_state(project, state)
    controller = CheckpointControl(project, state, config, intake, session, baseline, external)
    config.on_poll = controller.poll
    config.launch_guard = controller.launch_guard
    def record_probe(unit):
        state.update(probe_service=unit, probe_attempted=True)
        workspace.write_state(project, state)
    config.on_probe_launch = record_probe
    recorder = result = None
    code = 4
    try:
        with controller.launch_guard():
            pass
        state["backend"] = codex.verify_backend(config)
        with controller.launch_guard():
            pass
        state["capabilities"] = isolation.preflight(config, project)
        with codex.private_auth(project) as auth:
            if time.monotonic() >= config.deadline:
                raise TimeoutError("Active-work allowance exhausted during startup")
            def record_identity(identity):
                if identity and any(s.get("native_session_id") == identity for s in state["sessions"]):
                    raise workspace.InputError("Fresh context reused a previous native session identity")
                state["native_session_id"] = identity
                if state.get("rollover", {}).get("source_activation") == activation:
                    state["rollover"]["predecessor_native_session_id"] = identity
                elif previous:
                    state["rollover"].update(phase="continued", successor_native_session_id=identity)
                    state["sessions"][-1]["successor_native_session_id"] = identity
                workspace.write_state(project, state)
            def record_usage(usage):
                if isinstance(usage, dict):
                    for key, value in usage.items():
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            for field in ("usage_totals", "current_usage_totals"):
                                totals = state.get(field) or {}
                                totals[key] = totals.get(key, 0) + value
                                state[field] = totals
                else:
                    state["usage_complete"] = False
                # Persist completed-turn usage before another model turn.
                workspace.write_state(project, state)
            recorder = codex.EventRecorder(session, on_identity=record_identity, on_usage=record_usage)
            research_began = time.monotonic()
            config.deadline = min(investigation_deadline, research_began + config.primary_session_seconds)
            if config.deadline < investigation_deadline:
                controller.rollover_at = config.deadline - SAVING_GRACE
            # Crash accounting uses the effective session allocation, including startup.
            state.update(research_started_monotonic=research_began,
                         session_deadline_monotonic=config.deadline,
                         activation_allowance=max(0, config.deadline - began),
                         activation_deadline_epoch=began_epoch + max(0, config.deadline - began))
            # Durable launch intent precedes any spawn.
            state.update(state="running", reason="Primary researcher active.", service_attempted=True)
            workspace.write_state(project, state)
            result = isolation.run_isolated(
                config, project, codex.build_command(config),
                codex.build_prompt(intake, {**config.limits(),
                    "primary_session_policy": state["primary_session_policy"],
                    "remaining_wall_seconds": max(0, config.deadline-time.monotonic())}, continuation),
                recorder, auth)
            state["execution"] = asdict(result)
            state["cleanup_ok"] = result.cleanup_ok
            if not result.cleanup_ok:
                state.update(state="failed", reason="Cannot confirm service/descendant cleanup.")
            elif result.requested_stop:
                state.update(state="pausing" if result.requested_stop == "pause" else "rolling_over",
                             reason=f"Research service stopped for {result.requested_stop}.")
                code = 0
            elif result.interrupted:
                state.update(state="interrupted", reason="User interrupted; partial science retained.")
                code = 130
            elif result.timed_out:
                state.update(state="timed_out", reason="Active-work deadline reached; partial science retained.")
                code = 124
            elif result.returncode or result.error:
                state.update(state="failed", reason=result.error or
                             f"Codex/service exited {result.returncode}; inspect session stderr.txt.")
            else:
                state.update(state="completed", reason="Session ended; validating saved science.")
                code = 0
    except isolation.RequestedStop:
        state.update(state="pausing", reason="Suspension requested during startup.")
        code = 0
    except isolation.RuntimeUnavailable as exc:
        state.update(state="blocked", reason=str(exc))
        code = 3
    except TimeoutError as exc:
        state.update(state="timed_out", reason=str(exc))
        code = 124
    except KeyboardInterrupt:
        state.update(state="interrupted", reason="Interrupted; retained work may be incomplete.")
        code = 130
    except Exception as exc:
        state.update(state="failed", reason=f"{type(exc).__name__}: {exc}")
    finally:
        if recorder:
            recorder.close()
            telemetry = recorder.summary()
            state["telemetry"] = telemetry
            state["usage_complete"] &= telemetry["usage_complete"] and not (
                result is None or result.returncode or result.error or result.requested_stop)
            state["successful_commands"] = state.get("successful_commands", 0) + telemetry["successful_commands"]
        else:
            telemetry = {}
        if result is None:
            cleanup = []
            for key, attempted in (("service", "service_attempted"), ("probe_service", "probe_attempted")):
                if state[attempted]:
                    cleanup.append(isolation.stop_service(state[key]))
            state["cleanup_ok"] = all(cleanup)
        if not state["cleanup_ok"]:
            state.update(state="failed", reason=state["reason"] + " Cleanup could not be confirmed.")
            code = 4
        request = controller.current_request()
        rolling = bool(request and request["reason"] == "rollover")
        rollover_error = None
        prepared_valid = False
        if rolling:
            if controller.ack_deadline is None:
                rollover_error = "Saving was not acknowledged before closing the old session."
            elif not state["cleanup_ok"]:
                rollover_error = "Service/descendant cleanup unconfirmed."
            elif result is None or result.interrupted or result.error or result.returncode:
                rollover_error = "Old session failed or was interrupted during rollover."
            else:
                try:
                    workspace.load_prepared(project, state)
                    prepared_valid = True
                except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
                    rollover_error = f"Prepared checkpoint validation failed: {exc}"
        try:
            state["inputs_unchanged"] = workspace.fingerprints(project) == intake.fingerprints
            if not state["inputs_unchanged"]:
                state["pending_intake_changes"] = True
                if state["state"] == "completed" and not rolling:
                    state.update(state="incomplete", reason="Human inputs changed; reassessment required.")
                    code = 4
            if state["cleanup_ok"] and not (rolling and controller.ack_deadline is not None and not prepared_valid):
                conflicts = workspace.finalize_science(
                    project, state, intake, session, config.drafts, baseline, external,
                    expected=state.get("science_fingerprints", baseline))
                if state["state"] == "completed" and not rolling:
                    failures = workspace.validate_deliverables(project)
                    if not state.get("successful_commands"):
                        failures.append("No successful scientific command observed in this investigation")
                    if state.get("checkpoint_error"):
                        failures.append(state["checkpoint_error"])
                    if conflicts:
                        failures.append("Human note changes preserved; proposed replacements need reconciliation")
                    state["validation_failures"] = failures
                    state.update(state="incomplete" if failures else "completed",
                                 reason="; ".join(failures) if failures else
                                 "Checkpoint and structural artifact checks completed; science remains preliminary.")
                    code = 4 if failures else 0
                state["science_fingerprints"] = workspace.science_fingerprints(project)
        except (OSError, workspace.InputError, UnicodeError) as exc:
            state["checkpoint_error"] = f"Checkpoint finalization failed: {exc}"
            if state["state"] != "pausing":
                state.update(state="failed", reason=state["checkpoint_error"])
                code = 4
        ended = time.monotonic()
        charged = min(remaining, max(0, ended - began))
        state["active_seconds"] = min(config.wall_seconds, state.get("active_seconds", 0) + charged)
        state["activation_charged_seconds"] = charged
        state["remaining_active_seconds"] = max(0, config.wall_seconds - state["active_seconds"])
        state["accounting_pending"] = not state["cleanup_ok"]
        state["finished_at"] = now()
        # Registration and acknowledgement serialize with pause requests.
        with workspace.control_lock(project):
            request = controller.current_request()
            if state["cleanup_ok"] and ((request and request["reason"] == "pause")
                                       or state["state"] == "pausing"):
                state["previous_outcome"] = state["state"]
                state.update(state="paused", reason="Full suspension confirmed; all service descendants stopped.",
                             pause_request_id=request["request_id"] if request else state.get("pause_request_id"))
                code = 0
                if state.get("rollover", {}).get("source_activation") == activation or previous:
                    state["rollover"].update(phase="paused")
            elif rolling:
                summary = state.setdefault("rollover", {
                    "source_activation": activation, "request_id": request["request_id"]})
                if not rollover_error and state.get("checkpoint", {}).get("id") != activation:
                    rollover_error = state.get("checkpoint_error") or "No valid checkpoint published for ending session."
                if rollover_error:
                    summary.update(phase="failed", limitation=rollover_error)
                    state.update(state="failed", reason=f"Rollover failed: {rollover_error} Resume from saved science.")
                    code = 4
                elif time.monotonic() >= investigation_deadline:
                    summary.update(phase="exhausted", checkpoint_id=activation)
                    state.update(state="timed_out", reason="Active-work allowance exhausted after checkpoint.")
                    code = 124
                else:
                    summary.update(phase="checkpointed", checkpoint_id=activation)
                    state.update(state="rolling_over", reason="Checkpoint published; preparing fresh context.")
                    state["recovery_finalization_pending"] = {
                        "started_monotonic": ended,
                        "started_epoch": time.time() - max(0, time.monotonic() - ended),
                        "boot_id": boot_identity(), "allowance": state["remaining_active_seconds"]}
                    code = 0
            elif previous:
                if code not in (0, 124, 130) or not state["service_attempted"]:
                    state["rollover"].update(phase="failed", limitation=state["reason"])
                elif not state.get("native_session_id"):
                    state["rollover"].update(phase="continued_identity_unknown",
                                             limitation="Fresh native identity unavailable; live proof incomplete.")
            if state["cleanup_ok"]:
                state.pop("checkpoint_prepared", None)
            state["sessions"].append({"activation_id": activation, "native_session_id": state["native_session_id"],
                                      "outcome": state["state"], "active_seconds": charged,
                                      "service": state["service"] if state["service_attempted"] else None,
                                      "probe_service": state["probe_service"] if state["probe_attempted"] else None,
                                      "cleanup_ok": state["cleanup_ok"],
                                      "control_group": (result.service_properties.get("ControlGroup")
                                                        if result else None),
                                      "usage_totals": telemetry.get("usage_totals"),
                                      "checkpoint_id": state.get("checkpoint", {}).get("id"),
                                      "predecessor_activation": predecessor,
                                      "logs": session.relative_to(project).as_posix()})
            workspace.write_state(project, state)
    return code, controller, ended


def human_direction(project, source, feedback=False):
    project = validate_project(project)
    text = workspace.read_input(source)
    if not text.strip():
        raise workspace.InputError("Human contribution must not be empty")
    with workspace.acquire_project_lock(project):
        state = load_state(project)
        recover_owner(project, state)
        workspace.regular_tree(project / "starting_evidence")
        target = workspace.safe_path(project, "HUMAN_FEEDBACK.md" if feedback
                                     else "starting_evidence/RESEARCH_QUESTIONS.md")
        if feedback:
            previous = workspace.read_input(target) if target.exists() else "# Human scientific feedback\n"
            text = previous + f"\n\n## Human contribution ({now()})\n\n" + text + "\n"
        if len(text.encode("utf-8")) > 256 * 1024:
            raise workspace.InputError("Combined human input exceeds 256 KiB")
        workspace.atomic_text(target, text)
        state["pending_intake_changes"] = True
        workspace.write_state(project, state)
    print("Human direction saved; next resume reloads current inputs.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded scientific investigation with persistent checkpoints.")
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("start", help="start a fresh foreground investigation")
    launch.add_argument("project", type=Path)
    launch.add_argument("--codex", default="codex")
    launch.add_argument("--model")
    launch.add_argument("--wall-seconds", type=positive, default=600)
    launch.add_argument("--memory-mib", type=positive_int, default=2048)
    launch.add_argument("--max-tasks", type=positive_int, default=128)
    launch.add_argument("--primary-session-seconds", type=session_seconds, default=300)
    restart = sub.add_parser("resume", help="continue saved science in a fresh foreground context")
    restart.add_argument("project", type=Path)
    restart.add_argument("--codex", default="codex")
    restart.add_argument("--model")
    for name, option in (("redirect", "--questions-file"), ("feedback", "--file")):
        command = sub.add_parser(name, help="record human input while the project is quiescent")
        command.add_argument("project", type=Path)
        command.add_argument(option, dest="source", required=True, type=Path)
    show = sub.add_parser("inspect", help="inspect saved status without inference or authentication")
    show.add_argument("project", type=Path)
    show.add_argument("--json", action="store_true")
    suspend = sub.add_parser("pause", help="fully suspend research; wait up to 60 seconds for confirmation")
    suspend.add_argument("project", type=Path)
    args = parser.parse_args(argv)
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    try:
        if args.command == "pause":
            return pause(args.project)
        if args.command == "inspect":
            state = inspect_project(args.project)
            if args.json:
                print(json.dumps(state, indent=2))
            else:
                print(f"{state['state']}: {state.get('reason', '')}\n{state['activity_check']}")
                for key in ("limits", "primary_session_policy", "rollover", "sessions",
                            "remaining_active_seconds", "usage_totals", "usage_complete",
                            "checkpoint", "native_session_id", "pending_reconciliation",
                            "pending_intake_changes", "checkpoint_error", "checkpoint_prepared",
                            "previous_outcome", "interrupted_work", "recovery", "accounting_uncertainties"):
                    print(f"{key}: {json.dumps(state.get(key))}")
                for artifact in state.get("artifacts", []):
                    present = "present" if state["artifact_availability"][artifact] else "missing"
                    print(f"Artifact ({present}): {args.project / artifact}")
                for limitation in state.get("limitations", []):
                    print(f"Limitation: {limitation}")
            return 0
        if args.command in ("redirect", "feedback"):
            return human_direction(args.project, args.source, feedback=args.command == "feedback")
        if args.command == "resume":
            return resume(args.project, args.codex, args.model)
        config = isolation.Config(codex=args.codex, model=args.model, wall_seconds=args.wall_seconds,
                                  memory_mib=args.memory_mib, max_tasks=args.max_tasks,
                                  primary_session_seconds=args.primary_session_seconds)
        return start(args.project, config)
    except (workspace.InputError, OSError, ValueError, KeyError, argparse.ArgumentTypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGTERM, previous)


