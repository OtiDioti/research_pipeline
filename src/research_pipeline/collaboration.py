"""Foreground coordination of a bounded collection of scientific tasks.

Task identity and science outlive activations. Services, not nested controllers,
contain every backend and scientific descendant. No transcript is continuation input.
"""
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, replace
import json
import math
import os
from pathlib import Path
import re
import time
import uuid
from urllib.parse import unquote, urlsplit

from . import codex, isolation, verification, workspace, tools, jobs

SCIENCE_FIELDS = {
    "checkpoint", "checkpoints", "checkpoint_prepared", "checkpoint_error",
    "science_fingerprints", "external_changes", "pending_reconciliation", "preserved_edits",
    "pending_human_changes", "recovery", "interrupted_work", "input_fingerprints",
}
IDENTITY_FIELDS = {"task_id", "logical_researcher_id", "role", "objective", "scientific_benefit",
                   "parent_task", "assigning_primary", "workspace", "assignment", "status",
                   "delivery", "integration", "activation"}


class TaskState(dict):
    """A transient checkpoint view; durable science stays on the logical task."""
    def __init__(self, coordinator, task):
        self.coordinator, self.task = coordinator, task
        super().__init__(run_id=coordinator.state["run_id"],
                         ownership_nonce=coordinator.state["ownership_nonce"])
        self.update({k: v for k, v in task.items() if k != "activation"})
        self.update(task["activation"])

    def persist(self):
        for key in SCIENCE_FIELDS:
            if key in self:
                self.task[key] = self[key]
            else:
                self.task.pop(key, None)
        self.task["activation"] = {k: v for k, v in self.items()
                                  if k not in SCIENCE_FIELDS | IDENTITY_FIELDS | {"verification"}
                                  and k not in ("run_id", "ownership_nonce")}
        self.coordinator.save()


def new_task(task_id, objective, benefit, parent=None, assignment=None, role="researcher"):
    return {"task_id": task_id, "logical_researcher_id": task_id,
            "role": "primary" if task_id == "primary" else role,
            "objective": objective, "scientific_benefit": benefit, "parent_task": parent,
            "assigning_primary": "primary", "workspace": workspace.task_directory(task_id),
            "assignment": assignment, "status": "pending", "checkpoints": [], "activation": None,
            "delivery": None, "integration": []}


def validate_state(state, project):
    if state.get("project") != str(project) or state.get("schema_version") != 3:
        raise workspace.InputError("Invalid collaboration investigation identity")
    workspace.owner_fields(state)
    limits = state["limits"]
    jobs.validate_limits(limits)
    if limits["wall_seconds"] <= 0:
        raise workspace.InputError("Invalid saved wall allowance")
    for key in ("memory_mib", "max_tasks", "concurrent_researchers"):
        if not isinstance(limits[key], int) or isinstance(limits[key], bool) or limits[key] <= 0:
            raise workspace.InputError(f"Invalid saved {key}")
    if limits["memory_mib"] // limits["concurrent_researchers"] < 1 or limits["max_tasks"] // limits["concurrent_researchers"] < 1:
        raise workspace.InputError("Investigation limits produce zero slot shares")
    for value in (limits["wall_seconds"], state.get("active_seconds", 0)):
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise workspace.InputError("Invalid cumulative wall accounting")
    for policy in ("primary_session_policy", "delegated_session_policy"):
        value = state[policy]
        if value.get("mode") != "fixed_session_seconds" or not isinstance(value.get("session_seconds"), (int, float)) or not math.isfinite(value["session_seconds"]) or value["session_seconds"] <= 15:
            raise workspace.InputError("Invalid saved fixed session policy")
    tasks = state["tasks"]
    if "primary" not in tasks:
        raise workspace.InputError("Missing primary task")
    for task_id, task in tasks.items():
        if (task["task_id"] != task_id or task["logical_researcher_id"] != task_id
                or task["workspace"] != workspace.task_directory(task_id)
                or task["assigning_primary"] != "primary"
                or task["role"] not in (("primary",) if task_id == "primary" else ("researcher", "verifier"))
                or (task_id != "primary" and task["parent_task"] not in tasks)):
            raise workspace.InputError("Invalid saved task ownership")
        if task["role"] == "verifier":
            verification.validate_record(task)
            if tasks[task["parent_task"]]["role"] == "verifier":
                raise workspace.InputError("A verifier must check a research task")
    # Validate every unit before attempting cleanup, without opening any agent drafts.
    for activation in owned_activations(state):
        for key, flag in (("service", "service_attempted"), ("probe_service", "probe_attempted")):
            unit = activation.get(key)
            if (activation.get(flag) and not unit or unit and not re.fullmatch(r"research-[a-f0-9]{32}\.service", unit)):
                raise workspace.InputError("Invalid saved owned service")
    return state


def owned_activations(state):
    return [*state.get("sessions", []),
            *(t["activation"] for t in state["tasks"].values() if t.get("activation"))]


def settle_interval(state):
    interval = state.get("owner_interval")
    if not interval or not interval.get("pending"):
        return
    # Never use an ended primary's service timestamp to cap a concurrent owner.
    elapsed = max(0, time.time() - interval["started_epoch"])
    remaining = max(0, state["limits"]["wall_seconds"] - interval["initial_active_seconds"])
    charged = min(remaining, max(elapsed, state.get("active_seconds", 0) - interval["initial_active_seconds"]))
    state["active_seconds"] = interval["initial_active_seconds"] + charged
    state["remaining_active_seconds"] = remaining - charged
    interval["pending"] = False


def recover(project, state):
    """Stop all recorded work before inspecting any potentially malformed science."""
    unresolved = state.get("cleanup_ok") is not True or state["state"] in workspace.ACTIVE_STATES
    if unresolved:
        stopped, seen = True, set()
        for activation in owned_activations(state):
            clean = True
            for key, flag in (("probe_service", "probe_attempted"), ("service", "service_attempted")):
                unit = activation.get(key)
                if activation.get(flag) and unit not in seen:
                    seen.add(unit)
                    clean = isolation.stop_service(unit) and clean
            activation["cleanup_ok"] = clean
            stopped = clean and stopped
        if not stopped:
            state.update(state="failed", cleanup_ok=False, reason="Owned service cleanup unconfirmed; launch blocked.")
            workspace.write_state(project, state)
            raise workspace.InputError(state["reason"])
        settle_interval(state)
        state.update(state="interrupted", cleanup_ok=True, usage_complete=False,
                     reason="Lost controller recovered; all owned descendants stopped.")
        jobs.reconcile(state)
        state.setdefault("accounting_uncertainties", []).append(
            "Lost controller: owner elapsed wall charged once, capped at the original remaining grant. "
            "Unobserved usage and exact lost work remain unknown.")
        for task in state["tasks"].values():
            if task["status"] in ("running", "rolling_over", "starting"):
                task.update(status="interrupted", interrupted_work="Inspect saved science before restarting interrupted computation.")
        for task in state["tasks"].values():
            activation = task.get("activation")
            if activation and not any(s["activation_id"] == activation["activation_id"] for s in state["sessions"]):
                state["sessions"].append({**activation, "task_id": task["task_id"], "role": task["role"],
                    "parent_task": task["parent_task"], "outcome": "interrupted", "active_seconds": None,
                    "usage_totals": activation.get("current_usage_totals"),
                    "logs": f".research_pipeline/sessions/{activation['activation_id']}"})
        workspace.write_state(project, state)
    # A recovery can itself be interrupted after cleanup. Settle its durable interval.
    if state.get("owner_interval", {}).get("pending"):
        settle_interval(state)
        workspace.write_state(project, state)
    if state.get("cleanup_ok") is True:
        jobs.validate_limits(state["limits"], defaults=True)
    if not unresolved and not any(t.get("checkpoint_prepared") for t in state["tasks"].values()):
        return
    coordinator = Coordinator(project, state, isolation.Config())
    coordinator.begin_interval()
    try:
        for task in state["tasks"].values():
            if task.get("checkpoint_prepared") and task.get("activation"):
                view = TaskState(coordinator, task)
                try:
                    metadata, session, intake, accepted = workspace.load_prepared(project, view)
                    workspace.finalize_science(project, view, intake, session, session / "drafts",
                        metadata["baseline"], metadata["external_changes"],
                        expected=task.get("science_fingerprints"), accepted_intake=accepted,
                        task_id=task["task_id"])
                except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
                    view["checkpoint_error"] = f"Interrupted checkpoint finalization: {exc}; older handoff retained."
                view.pop("checkpoint_prepared", None)
                view.persist()
            if task["status"] != "completed":
                coordinator.recovery_handoff(task, task.get("interrupted_work", "Unfinished task; inspect saved science."))
    finally:
        coordinator.charge()
        state["owner_interval"]["pending"] = False
        coordinator.save()


class Coordinator:
    def __init__(self, project, state, config):
        self.project, self.state, self.base = project, state, config
        self.running = {}
        self.pause_deadline = None
        self.stop_reason = None
        self.began = None
        self.deadline = None
        self.jobs = jobs.JobManager(project, state, self.save)

    def save(self):
        workspace.write_state(self.project, self.state)

    def begin_interval(self):
        from .budget import boot_identity
        self.began = time.monotonic()
        self.initial_active = self.state.get("active_seconds", 0)
        remaining = max(0, self.state["limits"]["wall_seconds"] - self.initial_active)
        self.deadline = self.began + remaining
        self.state["owner_interval"] = {"started_epoch": time.time(), "pending": True,
            "initial_active_seconds": self.initial_active, "allowance": remaining,
            "started_monotonic": self.began, "boot_id": boot_identity()}
        self.save()

    def charge(self):
        self.state["active_seconds"] = min(self.state["limits"]["wall_seconds"],
            self.initial_active + max(0, time.monotonic() - self.began))
        self.state["remaining_active_seconds"] = max(0, self.state["limits"]["wall_seconds"] - self.state["active_seconds"])

    def global_request(self):
        _, control, _ = workspace.control_paths(self.project, self.state)
        request = workspace.read_control(control / "request.json")
        return request if workspace.matching_request(request, self.state) and request["reason"] == "pause" else None

    @contextmanager
    def launch_guard(self):
        with workspace.control_lock(self.project):
            if self.stop_reason or self.global_request() or time.monotonic() >= self.deadline:
                raise isolation.RequestedStop("pause" if self.global_request() else "stop")
            yield

    def summaries(self):
        summaries = []
        for task in self.state["tasks"].values():
            activation = task.get("activation") or {}
            summaries.append({k: task.get(k) for k in
                ("task_id", "role", "objective", "parent_task", "workspace", "status",
                 "assignment", "delivery", "integration", "checkpoint_error", "verification")}
                | {"handoff": workspace.handoff_path(task["task_id"]),
                   "activation_id": activation.get("activation_id"),
                   "predecessor_activation": activation.get("predecessor_activation"),
                   "rollover_at_monotonic": activation.get("rollover_at_monotonic")
                       if task["status"] == "running" else None,
                   "saving_reason": activation.get("saving_reason")
                       if task["status"] in ("running", "rolling_over") else None})
        return summaries

    def publish_status(self):
        text = json.dumps(self.summaries(), indent=2) + "\n"
        for runtime in self.running.values():
            workspace.atomic_text(runtime["config"].control / "tasks.json", text)

    def request_stop(self, reason):
        self.stop_reason = reason
        self.pause_deadline = self.pause_deadline or min(self.deadline, time.monotonic() + 15)
        self.state.update(state="pausing" if reason == "pause" else "running", reason=f"Saving all tasks for {reason}.")
        for runtime in self.running.values():
            runtime["control"].request("pause", self.pause_deadline)
        self.save()

    def poll_preparation(self, control):
        """Keep live contexts saving/draining while another slot is prepared."""
        self.jobs.poll()
        if self.global_request() and self.stop_reason != "pause":
            self.request_stop("pause")
        if time.monotonic() >= self.deadline and not self.stop_reason:
            self.request_stop("wall deadline")
        for task_id, runtime in list(self.running.items()):
            if runtime["service"].poll():
                self.finish(task_id)
                if task_id == "primary" and runtime["task"]["status"] != "rolling_over" and not self.stop_reason:
                    self.request_stop("primary ended with unfinished tasks")
        # Starting successors here would nest launch preparation. The outer loop
        # handles any acknowledged rollovers after this reserved slot is prepared.
        return control.poll(research=False) or ("pause" if self.stop_reason else None)

    def has_slot(self, task_id=None):
        # Preparation and an acknowledged rollover retain the task's allocation
        # even while no research service is present in running.
        occupied = set(self.running) | {
            task["task_id"] for task in self.state["tasks"].values()
            if task["status"] in ("starting", "rolling_over")}
        if task_id in self.running:
            return False
        occupied.discard(task_id)  # a successor reuses its own reserved slot
        return len(occupied) < self.state["limits"]["concurrent_researchers"]

    def launch(self, task):
        if not self.has_slot(task["task_id"]):
            raise workspace.InputError("No free researcher slot")
        with self.launch_guard():
            predecessor = task.get("activation")
            activation = uuid.uuid4().hex
            task["activation"] = {"activation_id": activation, "state": "starting",
                "service": f"research-{uuid.uuid4().hex}.service", "service_attempted": False,
                "probe_service": None, "probe_attempted": False, "cleanup_ok": True,
                "native_session_id": None, "predecessor_activation": predecessor["activation_id"] if predecessor else None,
                "started_monotonic": time.monotonic()}
            task["status"] = "starting"
            if predecessor:
                for previous in self.state["sessions"]:
                    if previous["activation_id"] == predecessor["activation_id"]:
                        previous["successor_activation"] = activation
            self.save()  # reserves a slot before any probe or backend spawn
        self.publish_status()  # Preparation polling must expose the reserved successor.
        view = TaskState(self, task)
        count = self.state["limits"]["concurrent_researchers"]
        config = replace(self.base, memory_mib=self.state["limits"]["memory_mib"] // count,
            max_tasks=self.state["limits"]["max_tasks"] // count, max_agents=count,
            deadline=self.deadline, unit=view["service"], task_id=task["task_id"],
            task_workspaces=("work/tasks",), launch_guard=self.launch_guard,
            frozen_inputs=(f"{task['workspace']}/inputs",) if task["role"] == "verifier" else ())
        session, config.control, config.response = workspace.control_paths(self.project, view)
        session.mkdir(parents=True)
        config.control.mkdir()
        config.response.mkdir()
        config.drafts = session / "drafts"
        config.drafts.mkdir()
        stack = ExitStack()
        recorder = None
        runtime = None
        control = TaskControl(self, view, config, None, session, {}, [])
        config.on_poll = lambda research=False: self.poll_preparation(control)
        try:
            if task["role"] == "verifier":
                verification.check_unchanged(self.project, task, self.deadline)
                if task["verification"]["phase"] not in ("initial", "reexamination"):
                    raise workspace.InputError("Verification is waiting or closed")
            intake = workspace.read_intake(self.project, self.deadline, config.on_poll)
            from . import references
            references.configure(config, self.project, session, intake)
            baseline = workspace.science_fingerprints(self.project, task["task_id"])
            external = sorted(set(workspace.changed_files(task.get("science_fingerprints", {}), baseline))
                              | set(task.get("pending_human_changes", [])))
            saved, handoff, historical = workspace.load_checkpoint(self.project, view)
            continuation = {"investigation_id": self.state["run_id"], "logical_researcher_id": task["task_id"],
                "parent_task": task["parent_task"], "workspace": task["workspace"],
                "handoff": handoff or "No valid checkpoint; inspect ordinary saved artifacts cautiously.",
                "previous_accepted_intake": historical, "external_markdown_changes_or_deletions": external,
                "input_changes": workspace.changed_files(saved["input_fingerprints"] if saved else {}, intake.fingerprints),
                "pending_reconciliation": task.get("pending_reconciliation", []),
                "tasks": self.summaries(), "interrupted_work": task.get("interrupted_work")}
            view["input_fingerprints"] = intake.fingerprints
            view.persist()
            control.intake, control.baseline, control.external = intake, baseline, external
            def probe_launch(unit):
                view.update(probe_service=unit, probe_attempted=True, cleanup_ok=False)
                view.persist()
            config.on_probe_launch = probe_launch
            self.state["backend"] = codex.verify_backend(config, on_wait=config.on_poll)
            self.state["capabilities"] = {**isolation.preflight(config, self.project),
                "investigation_grant": self.state["limits"],
                "slot_limits": {"memory_mib": config.memory_mib, "max_tasks": config.max_tasks, "swap_bytes": 0}}
            # A finished probe must not overlap its replacement research service.
            if view["probe_attempted"] and not isolation.stop_service(view["probe_service"]):
                raise isolation.RuntimeUnavailable("Probe cleanup unconfirmed")
            view["probe_cleanup_ok"] = True
            config.on_poll = control.poll
            auth = stack.enter_context(codex.private_auth(self.project))
            stack.enter_context(codex.native_tool_trace(auth, session))
            duration = self.state["primary_session_policy" if task["task_id"] == "primary" else "delegated_session_policy"]["session_seconds"]
            config.deadline = min(self.deadline, time.monotonic() + duration)
            tools.configure(config, self.project, session, activation)
            self.jobs.configure(config, session, view)
            # A model turn plus handoff validation can exceed the pause grace.
            # Reserve headroom *inside* the fixed session, never extend its cap.
            control.rollover_grace = min(60, max(15, duration / 4))
            control.rollover_at = config.deadline - control.rollover_grace if config.deadline < self.deadline else None
            def identity(value):
                all_ids = [a.get("native_session_id") for a in owned_activations(self.state)
                           if a.get("activation_id") != activation]
                if value and value in all_ids:
                    raise workspace.InputError("Fresh context reused a previous native session identity")
                view["native_session_id"] = value
                view.persist()
            def usage(value):
                if not isinstance(value, dict):
                    self.state["usage_complete"] = False
                else:
                    totals = self.state.get("usage_totals") or {}
                    current = view.get("current_usage_totals") or {}
                    for key, amount in value.items():
                        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
                            totals[key] = totals.get(key, 0) + amount
                            current[key] = current.get(key, 0) + amount
                    self.state["usage_totals"] = totals
                    view["current_usage_totals"] = current
                view.persist()
            recorder = codex.EventRecorder(session, on_identity=identity, on_usage=usage)
            workspace.atomic_text(config.control / "owner.json", json.dumps({**workspace.owner_fields(view), "task_id": task["task_id"]}))
            workspace.atomic_text(config.control / "tasks.json", json.dumps(self.summaries()))
            view.update(service_attempted=True, cleanup_ok=False, state="running",
                        session_deadline_monotonic=config.deadline,
                        rollover_at_monotonic=control.rollover_at,
                        rollover_saving_seconds=control.rollover_grace)
            task["status"] = "running"
            view.persist()
            service = isolation.RunningService(config, self.project, codex.build_command(config),
                codex.build_prompt(intake, {**self.state["limits"], "slot_memory_mib": config.memory_mib,
                    "slot_max_tasks": config.max_tasks, "session_seconds": duration,
                    "rollover_saving_seconds": control.rollover_grace,
                    "remaining_wall_seconds": max(0, self.deadline-time.monotonic())},
                    continuation, task), recorder, auth)
            runtime = {"service": service, "config": config, "control": control, "view": view,
                "intake": intake, "session": session, "baseline": baseline, "external": external,
                "stack": stack, "recorder": recorder, "task": task}
            self.running[task["task_id"]] = runtime
            self.publish_status()
        except BaseException as exc:
            clean = True
            for key, flag in (("probe_service", "probe_attempted"), ("service", "service_attempted")):
                if view.get(flag):
                    clean = isolation.stop_service(view[key]) and clean
            if recorder:
                recorder.close()
            stack.close()
            self.jobs.owner_stopped(activation, clean)
            view.update(cleanup_ok=clean, state="failed", error=f"{type(exc).__name__}: {exc}")
            task["status"] = "failed"
            view["checkpoint_error"] = f"Launch failed: {exc}; resume from saved science."
            view.persist()
            self.record_session(task, view)
            if clean:
                self.recovery_handoff(task, task["checkpoint_error"])
            if not clean:
                self.request_stop("cleanup failure")
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            if task["task_id"] == "primary" and not self.stop_reason:
                self.state.update(reason=str(exc), state="blocked" if isinstance(exc, isolation.RuntimeUnavailable) else "failed")
                self.request_stop("primary launch failed")

    def recovery_handoff(self, task, limitation):
        """Honest fallback guidance, never an acknowledged rollover checkpoint."""
        if task["task_id"] == "primary":
            return
        path = workspace.safe_path(self.project, workspace.handoff_path(task["task_id"]))
        if path.exists():
            return  # preserve researcher/human science, including an incomplete handoff
        text = (f"Logical researcher: {task['task_id']}\n\n## Objective\n{task['objective']}\n\n"
            f"## Parent question\nParent task: {task['parent_task']}; see the assignment.\n\n"
            f"## Completed\nController recovery summary only. No completed scientific result is certified.\n\n"
            f"## Artifacts\n[Assignment](/project/{task['assignment']}); inspect {task['workspace']}/ for partial work.\n\n"
            f"## Assumptions\nSee assignment; researcher assumptions may be incompletely saved.\n\n"
            f"## Unresolved\n{limitation}\n\n"
            "## Next action\nInspect retained artifacts and assignment before resuming this same task.\n\n"
            "## Interrupted computation\nUnknown; owned descendants have been stopped. Inspect partial outputs before repeating work.\n\n"
            "## Resume or reconsider\nReconsider the interrupted approach with the primary, then resume from valid saved science.\n")
        workspace.atomic_text(path, text)

    def record_session(self, task, view, telemetry=None):
        summary = {**task["activation"], "task_id": task["task_id"], "role": task["role"],
            "parent_task": task["parent_task"], "outcome": task["status"],
            "active_seconds": max(0, time.monotonic() - view["started_monotonic"]),
            "checkpoint_id": task.get("checkpoint", {}).get("id"),
            "usage_totals": (telemetry or {}).get("usage_totals"),
            "logs": f".research_pipeline/sessions/{view['activation_id']}"}
        self.state["sessions"] = [s for s in self.state["sessions"] if s["activation_id"] != summary["activation_id"]] + [summary]
        self.save()

    def finish(self, task_id):
        runtime = self.running[task_id]
        task, view, control = runtime["task"], runtime["view"], runtime["control"]
        result = runtime["service"].finish()
        self.jobs.owner_stopped(view["activation_id"], result.cleanup_ok)
        runtime["recorder"].close()
        telemetry = runtime["recorder"].summary()
        telemetry.update(jobs.observed(self.state, view["activation_id"]))
        runtime["stack"].close()
        self.state["usage_complete"] &= telemetry["usage_complete"] and not bool(result.error or result.returncode)
        view.update(execution=asdict(result), cleanup_ok=result.cleanup_ok, state="stopped",
                    telemetry=telemetry)
        rolling = bool(control.current_request() and control.current_request()["reason"] == "rollover")
        rollover_error = None
        if rolling:
            if control.ack_deadline is None:
                rollover_error = "Saving was not acknowledged before closure"
            elif not result.cleanup_ok or result.error or result.returncode or result.interrupted:
                rollover_error = "Old session failed or cleanup is unconfirmed"
            else:
                try:
                    workspace.load_prepared(self.project, view)
                except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
                    rollover_error = f"Prepared checkpoint changed: {exc}"
        if result.cleanup_ok:
            try:
                if workspace.fingerprints(self.project) != runtime["intake"].fingerprints:
                    self.state["pending_intake_changes"] = True
                if not (rolling and control.ack_deadline is not None and rollover_error):
                    workspace.finalize_science(self.project, view, runtime["intake"], runtime["session"],
                        runtime["config"].drafts, runtime["baseline"], runtime["external"],
                        task_id=task_id)
            except (OSError, ValueError, UnicodeError) as exc:
                view["checkpoint_error"] = f"Scientific publication failed: {exc}"
            if rolling and view.get("checkpoint", {}).get("id") != view["activation_id"]:
                rollover_error = view.get("checkpoint_error") or "No valid new checkpoint"
            view.pop("checkpoint_prepared", None)
        task["status"] = "paused" if self.stop_reason else "failed"
        if not self.stop_reason and rolling:
            task["status"] = "interrupted" if rollover_error else "rolling_over"
            view["rollover"] = {"phase": "failed" if rollover_error else "checkpointed",
                                "limitation": rollover_error, "source_activation": view["activation_id"]}
        elif not self.stop_reason and result.cleanup_ok and not (result.returncode or result.error or result.interrupted or result.timed_out):
            failures = [view["checkpoint_error"]] if view.get("checkpoint_error") else []
            if task["role"] == "verifier" and view.get("pending_reconciliation"):
                failures.append("Verifier drafts conflict with human edits; reassessment required")
            if task["role"] == "verifier" and not failures:
                try:
                    task["status"] = verification.deliver(self.project, task, self.deadline)
                except (OSError, ValueError, KeyError) as exc:
                    failures.append(f"Verification delivery failed: {exc}")
            elif task_id != "primary" and task["role"] != "verifier":
                path = f"{task['workspace']}/RESULT.md"
                try:
                    text = workspace.read_input(workspace.safe_path(self.project, path))
                    if not text.strip() or "preliminary" not in text.lower():
                        failures.append("Delivery must be substantive Markdown labeled preliminary")
                    else:
                        task["delivery"] = {"result": path, "handoff": workspace.handoff_path(task_id), "label": "preliminary"}
                except (OSError, ValueError) as exc:
                    failures.append(str(exc))
            if task["role"] != "verifier" or failures:
                task["status"] = "incomplete" if failures else "completed"
            if failures:
                view["checkpoint_error"] = "; ".join(failures)
        elif result.timed_out:
            task["status"] = "timed_out"
        if result.cleanup_ok and task["role"] == "researcher" and not task.get("delivery"):
            partial = f"{task['workspace']}/RESULT.md"
            if workspace.safe_path(self.project, partial).is_file():
                task["delivery"] = {"result": partial, "handoff": workspace.handoff_path(task_id),
                                    "label": "preliminary", "partial": True}
        view.persist()
        self.record_session(task, view, telemetry)
        if result.cleanup_ok and task["status"] != "completed":
            self.recovery_handoff(task, view.get("checkpoint_error") or "Task unfinished; progress may be partial.")
        del self.running[task_id]
        if not result.cleanup_ok:
            self.request_stop("cleanup failure")
        if task_id == "primary" and task["status"] != "rolling_over" and not self.stop_reason:
            if self.running:
                self.request_stop("primary ended with unfinished tasks")
        self.publish_status()

    def accept_assignment(self, runtime):
        if runtime["task"]["task_id"] != "primary":
            return
        request = workspace.read_control(runtime["config"].response / "delegation.json")
        if not request:
            return
        nonce = request.get("nonce")
        if not isinstance(nonce, str) or not re.fullmatch(r"[a-f0-9]{32}", nonce):
            return
        recorded = runtime["view"].setdefault("assignment_responses", {})
        if nonce in recorded:
            workspace.atomic_text(runtime["config"].control / "delegation-ack.json", json.dumps(recorded[nonce]))
            return
        ack = {"nonce": nonce, "accepted": False}
        try:
            with self.launch_guard():
                expected = {**workspace.owner_fields(runtime["view"]), "task_id": "primary"}
                if any(request.get(k) != v for k, v in expected.items()):
                    raise workspace.InputError("Assignment activation ownership mismatch")
                operation = request.get("operation", "delegate")
                if operation in ("verify", "respond", "close"):
                    task, should_launch = self.verification_request(request, runtime["config"].drafts)
                elif operation == "delegate":
                    task = self.delegation_request(request, runtime["config"].drafts)
                    should_launch = True
                else:
                    raise workspace.InputError("Unknown helper operation")
                ack.update(accepted=True, task_id=task["task_id"], workspace=task["workspace"])
                recorded[nonce] = ack
                runtime["view"].persist()  # durable acceptance before spawn
            if should_launch:
                self.launch(task)
        except (OSError, ValueError, KeyError, isolation.RequestedStop) as exc:
            ack["error"] = str(exc)
        recorded[nonce] = ack
        runtime["view"].persist()
        workspace.atomic_text(runtime["config"].control / "delegation-ack.json", json.dumps(ack))
        self.publish_status()

    def delegation_request(self, request, drafts):
        # Preserve the original researcher admission and retry rules.
        parent = request.get("parent_task")
        if parent not in self.state["tasks"]:
            raise workspace.InputError("Unknown scientific parent task")
        if not self.has_slot():
            raise workspace.InputError("All researcher slots allocated; continue parent work")
        task = next((t for t in self.state["tasks"].values()
                     if t.get("assignment") == request["assignment"]), None)
        if task is not None:
            if task["role"] != "researcher":
                raise workspace.InputError("Cannot delegate an existing verifier")
            if task["parent_task"] != parent or task["assigning_primary"] != "primary":
                raise workspace.InputError("Cannot change an existing task's parent or ownership")
            if task["status"] == "completed" or task["task_id"] in self.running:
                raise workspace.InputError("Existing task is completed or already active")
        else:
            task = self.read_assignment(request["assignment"], parent, drafts)
            self.state["tasks"][task["task_id"]] = task
        return task

    def verification_request(self, request, drafts):
        def retry(task):
            verification.check_unchanged(self.project, task, self.deadline)
            runnable = (task["verification"]["phase"] in ("initial", "reexamination")
                        and task["status"] in ("failed", "interrupted", "incomplete", "paused")
                        and task["task_id"] not in self.running)
            if runnable and not self.has_slot(task["task_id"]):
                raise workspace.InputError("All researcher slots allocated; accepted phase retained")
            return task, runnable

        operation = request["operation"]
        if operation == "verify":
            parent = request.get("parent_task")
            if parent not in self.state["tasks"] or self.state["tasks"][parent]["role"] == "verifier":
                raise workspace.InputError("Unknown scientific research parent")
            rel = request["assignment"]
            if not workspace.allowed_science(rel, "primary"):
                raise workspace.InputError("Verification packet must belong to the submitting primary")
            existing = next((t for t in self.state["tasks"].values() if t.get("verification", {}).get("packet_source") == rel), None)
            if existing:
                if existing["parent_task"] != parent:
                    raise workspace.InputError("Cannot change verifier parent or ownership")
                return retry(existing)  # same packet cannot manufacture another allowance
            if not self.has_slot():
                raise workspace.InputError("All researcher slots allocated; continue parent work")
            task_id = f"task-{uuid.uuid4().hex}"
            root = workspace.task_directory(task_id)
            packet, content = verification.freeze(self.project, rel, drafts, f"{root}/inputs/initial",
                                                  verification.PACKET_FIELDS, self.deadline)
            task = new_task(task_id, content["Claim and scope"], content["Scientific benefit"],
                            parent, f"{root}/ASSIGNMENT.md", role="verifier")
            task["verification"] = {"packet_source": rel, "initial": packet, "phase": "initial",
                "exchange_limit": 1, "response_committed": False, "disposition": "preliminary",
                "reviewed_version": packet["version"], "initial_check": None,
                "response": None, "final_check": None, "closure": None}
            workspace.atomic_text(self.project / task["assignment"],
                f"# Independent verification\n\nParent task: {parent}\n\n"
                f"Examine the [frozen scientific packet](/project/{packet['packet']}).\n"
                "Use your own reasoning/checks; do not edit original research or frozen inputs.\n")
            workspace.refresh_indexes(self.project, task_id=task_id)
            self.state["tasks"][task_id] = task
            return task, True
        task = self.state["tasks"].get(request.get("target"))
        if task is None or task["role"] != "verifier":
            raise workspace.InputError("Unknown verifier target")
        verification.check_unchanged(self.project, task, self.deadline)
        record = task["verification"]
        if record["phase"] == "closed":
            raise workspace.InputError("Closed verification exchanges cannot reopen")
        if operation == "respond" and record["response_committed"]:
            if request["response"] == record.get("response_source"):
                return retry(task)  # accepted phase can resume, never replace the response
            raise workspace.InputError("Verification response cannot be replaced")
        if record["phase"] != "awaiting_response" or task["task_id"] in self.running:
            raise workspace.InputError("Verification is not awaiting response; closed exchanges cannot reopen")
        rel = request["response"] if operation == "respond" else request["reason"]
        if not workspace.allowed_science(rel, "primary"):
            raise workspace.InputError("Verification response/closure must belong to primary")
        if operation == "respond":
            if not self.has_slot(task["task_id"]):
                raise workspace.InputError("All researcher slots allocated; response allowance unconsumed")
            packet, _ = verification.freeze(self.project, rel, drafts, f"{task['workspace']}/inputs/response",
                                            verification.RESPONSE_FIELDS, self.deadline)
            record.update(response=packet, response_source=rel, response_committed=True, phase="reexamination")
            task["status"] = "pending"
            return task, True
        path = workspace.safe_path(drafts, rel)
        if not path.exists():
            path = workspace.safe_path(self.project, rel)
        text = verification.read_bytes(path, self.deadline).decode("utf-8")
        if not text.strip() or Path(rel).suffix != ".md":
            raise workspace.InputError("Closure requires a substantive Markdown explanation")
        for target in verification.LINK.findall(text):
            candidate = verification.link_path(self.project, rel, target)
            if candidate is not None:
                if not workspace.safe_path(self.project, candidate).is_file():
                    raise workspace.InputError("Closure links must refer to saved canonical science")
                text = text.replace(f"]({target})", f"](/project/{candidate})")
        closure = f"{task['workspace']}/CLOSURE.md"
        workspace.atomic_text(self.project / closure,
            f"# Disputed: finite verification exchange closed\n\n{text}\n\n"
            f"Unresolved [independent objection](/project/{record['initial_check']}).\n")
        record.update(closure=closure, closure_sha256=workspace.file_digest(self.project / closure),
                      closure_source=rel, phase="closed", disposition="disputed")
        task.update(status="completed")
        task["delivery"]["label"] = "disputed"
        return task, False

    def read_assignment(self, rel, parent, drafts):
        canonical = workspace.safe_path(self.project, rel)
        if not workspace.allowed_science(rel, "primary") or canonical.suffix != ".md":
            raise workspace.InputError("Assignment must be primary scientific Markdown")
        path = workspace.safe_path(drafts, rel)
        if not path.exists():
            path = canonical
        text = workspace.read_input(path)
        sections = verification.sections(text, ("Objective", "Parent question", "Scientific benefit",
                                               "Assumptions", "Requested result", "Artifacts"))
        task_id = f"task-{uuid.uuid4().hex}"
        root = workspace.safe_path(self.project, workspace.task_directory(task_id))
        # Validate/copy draft inputs before accepting. Canonical science stays linked.
        copies = []
        for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", text):
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            link = unquote(url.path)
            candidate = Path(link.removeprefix("/project/")) if link.startswith("/project/") else Path(rel).parent / link
            resolved = Path(os.path.abspath(self.project / candidate))
            if not resolved.is_relative_to(self.project):
                raise workspace.InputError("Outside-project assignment artifact")
            candidate = resolved.relative_to(self.project).as_posix()
            source = workspace.safe_path(self.project, candidate)
            if not (candidate.startswith("starting_evidence/") or candidate == "AGENTS.md" or candidate == "HUMAN_FEEDBACK.md" or Path(candidate).parts[0] in workspace.MANAGED):
                raise workspace.InputError("Assignment references private operational files")
            proposed = workspace.safe_path(drafts, candidate)
            if proposed.exists() and workspace.allowed_science(candidate, "primary"):
                if proposed.suffix != ".md":
                    raise workspace.InputError("Only Markdown drafts are accepted assignment inputs")
                content = workspace.read_input(proposed)
                destination = f"{workspace.task_directory(task_id)}/assignment-input-{len(copies)}.md"
                copies.append((candidate, destination, content))
                replacement = "/project/" + destination
            elif source.is_file():
                replacement = "/project/" + candidate
            else:
                raise workspace.InputError(f"Missing assignment artifact: {candidate}")
            text = text.replace(f"]({target})", f"]({replacement})")
        mapped = {source: destination for source, destination, _ in copies}
        rewritten = []
        for source, destination, content in copies:
            for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", content):
                url = urlsplit(target)
                if url.scheme or url.netloc or not url.path:
                    continue
                link = unquote(url.path)
                relative = Path(link.removeprefix("/project/")) if link.startswith("/project/") else Path(source).parent / link
                absolute = Path(os.path.abspath(self.project / relative))
                if not absolute.is_relative_to(self.project):
                    raise workspace.InputError("Outside-project link in assignment input")
                canonical_rel = absolute.relative_to(self.project).as_posix()
                canonical_path = workspace.safe_path(self.project, canonical_rel)
                if canonical_rel in mapped:
                    final = mapped[canonical_rel]
                elif canonical_path.is_file() and (Path(canonical_rel).parts[0] in (*workspace.MANAGED, "starting_evidence")
                                                   or canonical_rel in ("AGENTS.md", "HUMAN_FEEDBACK.md", "RESEARCH_STATUS.md")):
                    final = canonical_rel
                else:
                    raise workspace.InputError("Assignment input links to unavailable science; include private draft dependencies explicitly in the assignment")
                content = content.replace(f"]({target})", f"](/project/{final})")
            rewritten.append((destination, content))
        root.mkdir(parents=True)
        for destination, content in rewritten:
            workspace.atomic_text(self.project / destination, content)
        assignment = f"{workspace.task_directory(task_id)}/ASSIGNMENT.md"
        workspace.atomic_text(self.project / assignment, text)
        workspace.refresh_indexes(self.project, task_id=task_id)
        return new_task(task_id, sections["Objective"], sections["Scientific benefit"], parent, assignment)

    def validate_integration(self):
        paths = workspace.science_fingerprints(self.project, "primary")
        failures = []
        for task in self.state["tasks"].values():
            if task["task_id"] == "primary":
                continue
            task["integration"] = []
            delivery = task.get("delivery")
            if task["status"] != "completed" or not delivery:
                failures.append(f"Unfinished delegated task: {task['task_id']}; inspect its handoff and saved artifacts")
                continue
            required = [delivery["result"]]
            if task["role"] == "verifier":
                record = task["verification"]
                try:
                    verification.check_unchanged(self.project, task, self.deadline)
                except (OSError, ValueError, KeyError) as exc:
                    record["integrity_error"] = str(exc)
                    failures.append(f"{task['task_id']}: {exc}")
                    continue
                record.pop("integrity_error", None)
                required = [record["initial_check"]]
                required += [record[key] for key in ("final_check", "closure") if record.get(key)]
                if record.get("response"):
                    required.append(record["response"]["packet"])
                # Endorsements apply only to the copied version, even after a human
                # or researcher changes the original. Surface this explicitly.
                reviewed = {e["source"]: e for key in ("initial", "response")
                            for e in (record.get(key) or {}).get("evidence", [])}
                record["changed_originals"] = [
                    e["source"] for e in reviewed.values()
                    if workspace.file_digest(workspace.safe_path(self.project, e["source"]), self.deadline)
                    != e["source_sha256"]]
            references = []
            linked = set()
            for rel in paths:
                if rel.startswith("handoffs/") or Path(rel).name == "FOLDER_CONTENT.md":
                    continue
                text = workspace.read_input_unbounded(self.project / rel)
                if task["role"] == "verifier":
                    # Links and outcome labels are structural requirements.
                    # Scientific explanations use ordinary prose; exact words
                    # cannot establish whether the findings were integrated.
                    if task["verification"]["disposition"] not in text.lower():
                        continue
                    if task["verification"].get("changed_originals") and "version" not in text.lower():
                        continue
                for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", text):
                    link = urlsplit(target)
                    if link.scheme or not link.path:
                        continue
                    path = self.project / link.path.removeprefix("/project/") if link.path.startswith("/project/") else self.project / Path(rel).parent / unquote(link.path)
                    matches = [r for r in required if path.resolve() == (self.project / r).resolve()]
                    if matches:
                        references.append(rel)
                        linked.update(matches)
            task["integration"] = sorted(set(references))
            if not references or linked != set(required):
                failures.append(f"No primary integration reference for {task['task_id']}")
        return failures

    def run(self):
        self.begin_interval()
        try:
            self.launch(self.state["tasks"]["primary"])
            for task in list(self.state["tasks"].values()):
                if (task["task_id"] != "primary" and task["status"] != "completed" and not self.stop_reason
                        and (task["role"] != "verifier"
                             or task["verification"]["phase"] in ("initial", "reexamination"))):
                    if self.has_slot(task["task_id"]):
                        self.launch(task)
                    else:
                        task["status"] = "interrupted"
                        task["interrupted_work"] = "No free slot on resume. Primary may explicitly resubmit this task's saved assignment to continue it."
                        self.save()
            while self.running or (not self.stop_reason and any(
                    task["status"] == "rolling_over" for task in self.state["tasks"].values())):
                self.jobs.poll()
                if self.global_request() and self.stop_reason != "pause":
                    self.request_stop("pause")
                if time.monotonic() >= self.deadline and not self.stop_reason:
                    self.request_stop("wall deadline")
                for task in list(self.state["tasks"].values()):
                    if task["status"] == "rolling_over" and task["task_id"] not in self.running and not self.stop_reason:
                        self.launch(task)
                for task_id, runtime in list(self.running.items()):
                    if self.running.get(task_id) is not runtime:
                        continue  # launch preparation may already have finished it
                    if runtime["service"].poll():
                        self.finish(task_id)
                        task = self.state["tasks"][task_id]
                        if task["status"] == "rolling_over" and not self.stop_reason:
                            self.launch(task)
                    elif not self.stop_reason:
                        self.accept_assignment(runtime)
                self.charge()
                time.sleep(.05)
        except isolation.RequestedStop:
            self.request_stop("pause" if self.global_request() else "wall deadline")
        except KeyboardInterrupt:
            self.request_stop("interrupted")
        except Exception as exc:
            self.state["reason"] = f"{type(exc).__name__}: {exc}"
            self.request_stop("controller failure")
        finally:
            # Exception/interrupt cleanup does not grant a sequential grace per child.
            finalization_errors = []
            for task_id in list(self.running):
                try:
                    self.finish(task_id)
                except Exception as exc:
                    runtime = self.running[task_id]
                    task = self.state["tasks"][task_id]
                    task["checkpoint_error"] = f"Finalization failed: {exc}"
                    finalization_errors.append(task["checkpoint_error"])
                    clean = True
                    for key, flag in (("probe_service", "probe_attempted"), ("service", "service_attempted")):
                        if task["activation"].get(flag):
                            clean = isolation.stop_service(task["activation"][key]) and clean
                    task["activation"]["cleanup_ok"] = clean
                    runtime["recorder"].close()
                    runtime["stack"].close()
            clean = all(a.get("cleanup_ok") is True for a in owned_activations(self.state))
            self.state["cleanup_ok"] = clean
            self.charge()
            self.state["owner_interval"]["pending"] = not clean
            if clean:
                try:
                    workspace.refresh_indexes(self.project)
                except (OSError, ValueError, UnicodeError) as exc:
                    finalization_errors.append(f"Index reconciliation failed: {exc}")
            if not clean:
                self.state.update(state="failed", reason="Full cleanup unconfirmed; no further launch permitted.")
                code = 4
            elif self.stop_reason:
                if self.stop_reason == "pause":
                    self.state.update(state="paused", reason="Full suspension confirmed; all owned services and descendants stopped.")
                    code = 0
                else:
                    outcome = ("timed_out" if self.stop_reason == "wall deadline" else
                               "blocked" if self.stop_reason == "primary launch failed" else "incomplete")
                    self.state.update(state=outcome,
                                      reason=f"Stopped: {self.stop_reason}. Inspect per-task recovery guidance.")
                    code = 124 if self.stop_reason == "wall deadline" else 3 if outcome == "blocked" else 4
            else:
                try:
                    failures = (finalization_errors
                                + workspace.validate_deliverables(self.project,
                                    labels=("preliminary", "checked", "disputed", "superseded"))
                                + self.validate_integration())
                except (OSError, ValueError, UnicodeError) as exc:
                    failures = [f"Final validation failed: {exc}"]
                if self.state.get("pending_intake_changes"):
                    failures.append("Human inputs changed during execution; resume for reassessment")
                primary = self.state["tasks"]["primary"]
                if primary["status"] != "completed":
                    failures.append(primary.get("checkpoint_error") or "Primary task incomplete")
                if not any(s.get("telemetry", {}).get("successful_commands", 0)
                           for s in self.state["sessions"] if s.get("task_id") == "primary"):
                    failures.append("No successful primary scientific command observed")
                self.state.update(state="incomplete" if failures else "completed", validation_failures=failures,
                    reason="; ".join(failures) if failures else "Research and verification deliveries integrated with scoped labels. Structural checks do not establish scientific correctness.")
                code = 4 if failures else 0
            self.charge()
            self.save()
        return code


class TaskControl:
    def __init__(self, coordinator, view, config, intake, session, baseline, external):
        self.coordinator, self.view, self.config = coordinator, view, config
        self.intake, self.session, self.baseline, self.external = intake, session, baseline, external
        self.deadline = self.ack_deadline = self.rollover_at = None
        self.rollover_grace = 15
        self.last_readiness = None

    def current_request(self):
        value = workspace.read_control(self.config.control / "request.json")
        return value if workspace.matching_request(value, self.view) else None

    def request(self, reason, deadline=None):
        request = self.current_request()
        if request and (request["reason"] == "pause" or reason == request["reason"]):
            return
        request = {"version": 1, **workspace.owner_fields(self.view), "reason": reason,
                   "request_id": request["request_id"] if request else uuid.uuid4().hex}
        workspace.atomic_text(self.config.control / "request.json", json.dumps(request))
        self.deadline = min(self.deadline or math.inf, deadline or math.inf,
                            self.config.deadline, time.monotonic() +
                            (self.rollover_grace if reason == "rollover" else 15))
        self.view["saving_reason"] = reason
        self.view.persist()
        self.coordinator.publish_status()

    def poll(self, research=True):
        self.coordinator.jobs.poll()
        if any(r["state"] == "cleanup_unconfirmed" and r["activation_id"] == self.view["activation_id"]
               for r in self.coordinator.state.get("jobs", {}).values()):
            raise isolation.RuntimeUnavailable("Previous job cleanup unconfirmed; stopping owning service.")
        if self.coordinator.global_request():
            if self.coordinator.stop_reason != "pause":
                self.coordinator.request_stop("pause")
            self.request("pause", self.coordinator.pause_deadline)
        if research and self.rollover_at is not None and time.monotonic() >= self.rollover_at and not self.coordinator.stop_reason:
            self.request("rollover")
        request = self.current_request()
        if not request:
            return None
        if not research:
            return request["reason"]
        self.deadline = self.deadline or min(self.config.deadline, time.monotonic() +
            (self.rollover_grace if request["reason"] == "rollover" else 15))
        if time.monotonic() >= (self.ack_deadline or self.deadline):
            return request["reason"]
        ready = workspace.read_control(self.config.response / "ready.json")
        nonce = ready.get("readiness_nonce") if ready else None
        if (ready and all(ready.get(k) == v for k, v in request.items()) and isinstance(nonce, str)
                and re.fullmatch(r"[a-f0-9]{32}", nonce) and nonce != self.last_readiness and self.ack_deadline is None):
            self.last_readiness = nonce
            ack = {**ready, "accepted": False}
            try:
                workspace.prepare_checkpoint(self.coordinator.project, self.view, self.intake,
                    self.session, self.config.drafts, self.baseline, self.external,
                    deadline=self.deadline, task_id=self.view["task_id"])
                workspace.check_deadline(self.deadline)
                ack["accepted"] = True
                self.ack_deadline = min(self.deadline, time.monotonic() + 1)
            except (OSError, ValueError, UnicodeError, TimeoutError) as exc:
                ack["error"] = str(exc)[:1000]
            workspace.atomic_text(self.config.control / "ack.json", json.dumps(ack))
        return None


def activate(project, config, state=None):
    """Caller owns run.lock. Resume cannot enlarge the original grant."""
    from .cli import now
    setup_started = time.monotonic()
    if state is None:
        workspace.validate_fresh(project)
        intake = workspace.read_intake(project, setup_started + config.wall_seconds)
        state = {"schema_version": 3, "project": str(project), "run_id": uuid.uuid4().hex,
            "started_at": now(), "limits": config.limits(), "sessions": [], "tasks": {},
            "primary_session_policy": {"mode": "fixed_session_seconds", "session_seconds": config.primary_session_seconds},
            "delegated_session_policy": {"mode": "fixed_session_seconds", "session_seconds": config.delegated_session_seconds},
            "active_seconds": 0, "usage_totals": None, "usage_complete": True,
            "artifacts": list(workspace.REQUIRED), "limitations": codex.LIMITATIONS}
        for name in workspace.MANAGED:
            (project / name).mkdir()
        (project / "work/tasks").mkdir()
        workspace.initial_status(project)
        workspace.refresh_indexes(project)
        state["tasks"]["primary"] = new_task("primary", intake.questions, "Own the evolving investigation and integrate findings")
    if state["limits"]["wall_seconds"] <= state.get("active_seconds", 0):
        raise workspace.InputError("Investigation active-work allowance exhausted; resume cannot enlarge limits")
    state.pop("pending_intake_changes", None)
    state.update(ownership_nonce=uuid.uuid4().hex, state="starting", cleanup_ok=True,
                 reason="Preparing task contexts from saved science.")
    _, control, _ = workspace.control_paths(project, state)
    control.mkdir(parents=True)
    workspace.write_state(project, state)
    state["active_seconds"] = min(state["limits"]["wall_seconds"],
        state.get("active_seconds", 0) + max(0, time.monotonic() - setup_started))
    coordinator = Coordinator(project, state, config)
    code = coordinator.run()
    print(f"{state['state']}: {state['reason']}\nStatus: {project / 'RESEARCH_STATUS.md'}")
    return code
