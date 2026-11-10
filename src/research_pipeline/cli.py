"""Foreground start and read-only inspection of one fresh investigation."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from . import codex, isolation, workspace


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
    state["activity_check"] = "Terminal state recorded; no live session requested."
    if state.get("state") in ("starting", "running"):
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


def start(project, config):
    project = Path(os.path.abspath(project))
    if not project.is_dir() or any(p.is_symlink() for p in (project, *project.parents)):
        raise workspace.InputError("Project must be an existing directory with no symlink ancestors")
    # Lock before freshness checks so concurrent starts receive the actual conflict.
    with workspace.acquire_project_lock(project):
        intake = workspace.read_intake(project)
        if (project / ".research_pipeline/run.json").exists():
            raise workspace.InputError("A run already exists; M1 requires a fresh project")
        config.deadline = time.monotonic() + config.wall_seconds
        state = {"schema_version": 1, "run_id": uuid.uuid4().hex, "project": str(project),
                 "started_at": now(), "state": "starting", "reason": "Checking runtime prerequisites.",
                 "limits": config.limits(), "capabilities": {}, "service": config.unit,
                 "backend": {}, "artifacts": list(workspace.REQUIRED), "validation_failures": [],
                 "input_fingerprints": intake.fingerprints, "input_inventory": intake.inventory,
                 "limitations": codex.LIMITATIONS, "cleanup_ok": None, "service_attempted": False}
        recorder = None
        result = None
        code = 4
        for name in workspace.MANAGED:
            (project / name).mkdir()
        workspace.write_state(project, state)
        workspace.refresh_indexes(project)
        try:
            state["backend"] = codex.verify_backend(config)
            state["capabilities"] = isolation.preflight(config, project)
            with codex.private_auth(project) as auth:
                if time.monotonic() >= config.deadline:
                    state.update(state="timed_out", reason="Wall budget exhausted during startup.")
                    code = 124
                else:
                    recorder = codex.EventRecorder(project / ".research_pipeline")
                    state.update(state="running", reason="One Codex research session is active.")
                    workspace.write_state(project, state)
                    state["service_attempted"] = True
                    result = isolation.run_isolated(config, project, codex.build_command(config),
                                                    codex.build_prompt(intake, {**config.limits(),
                                                        "remaining_wall_seconds": max(0, config.deadline-time.monotonic())}),
                                                    recorder, auth)
                    state["execution"] = asdict(result)
                    state["cleanup_ok"] = result.cleanup_ok
                    if not result.cleanup_ok:
                        state.update(state="failed", reason="Cannot confirm service/descendant cleanup.")
                        code = 4
                    elif result.interrupted:
                        state.update(state="interrupted", reason="User interrupted; partial artifacts retained.")
                        code = 130
                    elif result.timed_out:
                        state.update(state="timed_out", reason="Aggregate wall deadline reached; partial artifacts retained.")
                        code = 124
                    elif result.returncode:
                        state.update(state="failed", reason=result.error or
                                     f"Codex/service exited {result.returncode}; inspect stderr.txt.")
                        code = 4
                    else:
                        failures = workspace.validate_deliverables(project)
                        if not recorder.successful_commands:
                            failures.append("No successful scientific command observed in Codex events")
                        state["validation_failures"] = failures
                        state.update(state="incomplete" if failures else "completed",
                                     reason="; ".join(failures) if failures else
                                     "Session and structural artifact checks completed; findings remain preliminary.")
                        code = 4 if failures else 0
        except isolation.RuntimeUnavailable as exc:
            state.update(state="blocked", reason=str(exc))
            code = 3
        except TimeoutError as exc:
            state.update(state="timed_out", reason=str(exc))
            code = 124
        except KeyboardInterrupt:
            state.update(state="interrupted", reason="Interrupted during startup or finalization; partial work retained.")
            code = 130
        except Exception as exc:
            state.update(state="failed", reason=f"{type(exc).__name__}: {exc}")
            code = 4
        finally:
            if recorder:
                recorder.close()
                state["telemetry"] = recorder.summary()
            # run_isolated always cleans the service even if its event callback fails.
            # No service has been started when preflight fails its environment gate.
            if result is None and state["service_attempted"]:
                state["cleanup_ok"] = isolation.stop_service(config.unit)
                if not state["cleanup_ok"]:
                    state.update(state="failed", reason=state["reason"] + " Cleanup could not be confirmed.")
                    code = 4
            try:
                state["inputs_unchanged"] = workspace.fingerprints(project) == intake.fingerprints
                if not state["inputs_unchanged"]:
                    state.update(state="incomplete", reason="Human inputs changed during the run; findings require reassessment.")
                    code = 4
            except (OSError, workspace.InputError) as exc:
                state.update(state="incomplete", inputs_unchanged=False,
                             reason=f"Cannot confirm protected input integrity: {exc}")
                code = 4
            state["finished_at"] = now()
            try:
                # Index only at quiescent checkpoints. Never traverse live,
                # agent-mutated paths in the host controller.
                workspace.refresh_indexes(project, include_science=state["cleanup_ok"] is not False)
            except (OSError, workspace.InputError) as exc:
                state.update(state="failed", reason=f"Artifact index finalization failed: {exc}")
                code = 4
            workspace.write_state(project, state)
        print(f"{state['state']}: {state['reason']}\nStatus: {project / 'RESEARCH_STATUS.md'}")
        return code


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one bounded Codex scientific investigation (M1).")
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("start", help="start a fresh foreground investigation")
    launch.add_argument("project", type=Path)
    launch.add_argument("--codex", default="codex")
    launch.add_argument("--model")
    launch.add_argument("--wall-seconds", type=positive, default=600)
    launch.add_argument("--memory-mib", type=positive_int, default=2048)
    launch.add_argument("--max-tasks", type=positive_int, default=128)
    launch.add_argument("--cpu-percent", type=positive_int, default=100)
    show = sub.add_parser("inspect", help="inspect saved status without inference or authentication")
    show.add_argument("project", type=Path)
    show.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    try:
        if args.command == "inspect":
            state = inspect_project(args.project)
            if args.json:
                print(json.dumps(state, indent=2))
            else:
                print(f"{state['state']}: {state.get('reason', '')}")
                print(state["activity_check"])
                print("Limits: " + json.dumps(state.get("limits", {})))
                for artifact in state.get("artifacts", []):
                    present = "present" if state["artifact_availability"][artifact] else "missing"
                    print(f"Artifact ({present}): {args.project / artifact}")
                for limitation in state.get("limitations", []):
                    print(f"Limitation: {limitation}")
            return 0
        config = isolation.Config(codex=args.codex, model=args.model, wall_seconds=args.wall_seconds,
                                  memory_mib=args.memory_mib, max_tasks=args.max_tasks,
                                  cpu_percent=args.cpu_percent)
        return start(args.project, config)
    except (workspace.InputError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGTERM, previous)
