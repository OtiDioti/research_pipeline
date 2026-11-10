"""Opt-in real M2 continuity gate. Codex supplies all science, never a worker double."""
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import quote

from tests import use_checkout

use_checkout()
from research_pipeline import codex, isolation, workspace


INTERFACE = """
Author and execute standard-library Python work/compute.py accepting:
python3 /project/work/compute.py --a 1.1 2.0 --n 16 32 64 128 256 512 \
--output /project/work/baseline.json
Save JSON {"rows": [{"a": ..., "n": ..., "estimate": ...}, ...]} containing
actual periodic trapezoidal estimates on the requested grid. Allow other parameters
and output paths for reproduction. Supply no analytical answer in place of quadrature.
The command illustrates the interface; on continuation use the NEW requested
parameter/output combinations and preserve the existing baseline.
Save useful drafts EARLY: work/PLAN.md, work/DERIVATION.md, outputs/REPORT.md,
sources/LITERATURE.md and a linked handoff. Report actual literature access honestly.
Continue meaningful convergence, sensitivity and floating-point analysis until the
controller asks for a checkpoint; do not sleep or fabricate work to wait for it.
"""

QUESTIONS = """# Periodic quadrature
Investigate I(a) = integral from 0 to 2*pi of 1/(a-cos(theta)) dtheta, a > 1.
Derive a reference/error argument and compute a baseline convergence study for
a=1.1 and 2.0, n=16,32,64,128,256,512. Explain assumptions and numerical limitations.
Treat comparison with Simpson quadrature as a separate PENDING objective; establish
the baseline first. Save baseline.json and never replace it on continuation.
""" + INTERFACE

REVISED = """# Revised periodic quadrature objectives
Retain the established baseline findings and baseline.json without recomputing or
replacing them. REMOVE the pending Simpson comparison from the active plan.
ADD near-singular convergence for a=1.01, n=16,32,64,128,256,512, saved separately
in work/near.json. Reassess the error argument using this new numerical evidence.
Read current instructions, distinct HUMAN_FEEDBACK.md and the human derivation edit.
Explain the scientific consequences in work/CONTINUITY.md with sections:
## Retained findings
## Revised plan
## Human note and error interpretation
Give substantive explanations with links to baseline.json, near.json and DERIVATION.md.
Distinguish removed objectives from pending ones; do not just repeat input keywords.

This foreground resume will automatically roll over into a fresh conversation.
BEFORE that automatic rollover, continue useful near-singular analysis, save
assumptions and artifacts, and put a concrete next computation for a=1.001 in the
handoff's Next action. Reserve a=1.001 for the AUTOMATIC SUCCESSOR, not this explicit
resume session. Do not finish early while there is meaningful analysis to save.
AFTER that automatic rollover, use that handoff and saved evidence to compute
a=1.001, n=64,128,256,512,1024,2048,4096 into work/successor.json. Extend the
derivation, continuity note and report with the new result and its interpretation.
""" + INTERFACE

INSTRUCTIONS = "Use deterministic standard-library calculations. Report limitations honestly.\n"
NEW_INSTRUCTIONS = INSTRUCTIONS + "Report both absolute and relative quadrature errors.\n"
FEEDBACK = """Separate resolved truncation error from floating-point effects.
Use coarse and fine grids to justify any claimed floating-point plateau.
"""


@unittest.skipUnless(os.environ.get("RESEARCH_PIPELINE_M2_LIVE") == "1",
                     "Live M2 requires explicit RESEARCH_PIPELINE_M2_LIVE=1; no inference started")
class LiveM2Acceptance(unittest.TestCase):
    def test_real_pause_direction_and_automatic_fresh_continuation(self):
        output = os.environ.get("RESEARCH_PIPELINE_M2_OUTPUT_DIR")
        self.assertTrue(output, "Enabled live M2 requires RESEARCH_PIPELINE_M2_OUTPUT_DIR")
        began = time.monotonic()
        deadline = began + 1500
        # Seven expected services can each require several bounded systemctl calls.
        work_deadline = deadline - 400
        base = Path(output).absolute()
        base.mkdir(parents=True, exist_ok=True)
        run = Path(tempfile.mkdtemp(prefix="m2-live-", dir=base))
        run.chmod(0o700)
        project = run / "project"
        (project / "starting_evidence").mkdir(parents=True)
        (project / "starting_evidence/RESEARCH_QUESTIONS.md").write_text(QUESTIONS)
        (project / "starting_evidence/NOTE.md").write_text(
            "# Hypothesis\nNearby complex singularities may affect convergence. Test this conjecture.\n")
        (project / "AGENTS.md").write_text(INSTRUCTIONS)
        expected_inputs = workspace.fingerprints(project)
        receipt = {
            "invocation": run.name, "project": str(project), "started_at": time.time(),
            "bounds_seconds": {"active": 900, "session": 240, "reproduction": 60, "whole": 1500},
            "commands": [], "phases": {}, "services": {}, "cleanup": {},
            "limitations": codex.LIMITATIONS, "outcome": "failed",
            "inputs": {"old_questions": QUESTIONS, "old_instructions": INSTRUCTIONS},
        }
        processes = []
        reproduction = None
        primary_error = None
        print(f"\nM2 private acceptance artifacts: {run}", flush=True)

        def budget(seconds, cleanup=False):
            remaining = (deadline if cleanup else work_deadline) - time.monotonic()
            self.assertGreater(remaining, 0, "M2 outer deadline exhausted")
            return min(seconds, remaining)

        def read(rel):
            path = workspace.safe_path(project, rel)
            self.assertTrue(path.is_file(), f"Missing regular evidence: {rel}")
            self.assertLessEqual(path.stat().st_size, 4 * 1024 * 1024, f"Oversize evidence: {rel}")
            return path.read_text()

        def state():
            if not (project / ".research_pipeline/run.json").exists():
                raise FileNotFoundError("Investigation state not written yet")
            return json.loads(read(".research_pipeline/run.json"))

        def session_path(s):
            return f".research_pipeline/sessions/{s['activation_id']}"

        def remember(s, observe=True):
            # Read-only observation; never repair a false suspension before checking it.
            entries = [s, *s.get("sessions", [])]
            for entry in entries:
                for key in ("service", "probe_service"):
                    unit = entry.get(key)
                    attempted = entry.get("service_attempted" if key == "service" else "probe_attempted",
                                          True)
                    if not unit or not attempted:
                        continue
                    info = receipt["services"].setdefault(unit, {"groups": []})
                    group = entry.get("control_group")
                    if group and group not in info["groups"]:
                        info["groups"].append(group)
            if observe:
                for unit, info in receipt["services"].items():
                    if info.get("observed"):
                        continue
                    props = isolation.service_properties(unit)
                    info["observed"] = props
                    group = props.get("ControlGroup")
                    if group and group not in info["groups"]:
                        info["groups"].append(group)
                    # Retry observation if the durable intent preceded spawning.
                    may_launch = (unit == s.get("service") and s["state"] in workspace.ACTIVE_STATES
                                  or unit == s.get("probe_service") and s["state"] == "starting")
                    if props.get("LoadState") == "not-found" and may_launch:
                        info.pop("observed")

        def capture(name, s):
            remember(s)
            snapshot = run / f"{name}.json"
            snapshot.write_text(json.dumps(s, indent=2) + "\n")
            receipt["phases"][name] = {"snapshot": str(snapshot), "state": s}
            if name in ("paused", "final"):
                for rel in ("work/PLAN.md", "work/DERIVATION.md", "work/CONTINUITY.md", "outputs/REPORT.md"):
                    if (project / rel).is_file():
                        receipt.setdefault("scientific_observations", {})[f"{name}/{rel}"] = read(rel)[:3500]
            return s

        def launch(args, name, background=False, timeout=20):
            record = {"argv": args, "command": shlex.join(args),
                      "stdout": str(run / f"{name}.stdout"),
                      "stderr": str(run / f"{name}.stderr")}
            receipt["commands"].append(record)
            print(f"M2 command: {record['command']}", flush=True)
            with open(record["stdout"], "wb") as out, open(record["stderr"], "wb") as err:
                process = subprocess.Popen(args, stdout=out, stderr=err)
            processes.append((process, record))
            if background:
                return process
            record["returncode"] = process.wait(timeout=budget(timeout))
            self.assertEqual(record["returncode"], 0, f"CLI failed; see {record['stderr']}")
            return process

        def cli(command, *args):
            return [sys.executable, "-m", "research_pipeline", command, str(project), *args]

        def poll(process, check, seconds, label):
            end = time.monotonic() + budget(seconds)
            while time.monotonic() < end:
                try:
                    s = state()
                except (OSError, ValueError):
                    # Atomic state writes; initial file may not yet exist.
                    if process.poll() is not None:
                        self.fail(f"{label}: foreground exited {process.returncode}; see {run}")
                    time.sleep(.2)
                    continue
                activations = {s["activation_id"], *(entry["activation_id"] for entry in s["sessions"])}
                self.assertLessEqual(len(activations), 3, "Unexpected extra automatic sessions")
                remember(s)
                result = check(s)
                if result:
                    return capture(label, s)
                if process.poll() is not None:
                    self.fail(f"{label}: foreground exited {process.returncode}: {s.get('reason')}")
                time.sleep(.2)
            self.fail(f"Timed out waiting for {label}; see {run}")

        def events(s):
            path = project / session_path(s) / "backend.jsonl"
            if not path.exists():
                return []
            result = []
            for line in read(str(path.relative_to(project))).splitlines():
                try:
                    result.append(json.loads(line))
                except ValueError:
                    pass  # The current last event can be partially written.
            return result

        def successful(s, filename):
            return any(e.get("type") == "item.completed"
                       and e.get("item", {}).get("type") == "command_execution"
                       and e["item"].get("exit_code") == 0
                       and filename in e["item"].get("command", "")
                       for e in events(s))

        def has_json(rel):
            if not (project / rel).exists():
                return False
            try:
                return bool(json.loads(read(rel)).get("rows"))
            except ValueError:
                return False

        def rows(rel, aa, nn):
            values = {}
            payload = json.loads(read(rel))
            self.assertEqual(len(payload["rows"]), len(aa) * len(nn), rel)
            for row in payload["rows"]:
                a, n, estimate = row["a"], row["n"], row["estimate"]
                self.assertIn(a, aa)
                self.assertIn(n, nn)
                self.assertNotIn((a, n), values)
                self.assertTrue(math.isfinite(estimate) and estimate > 0)
                values[a, n] = estimate
            observations = {}
            for a in aa:
                reference = 2 * math.pi / math.sqrt(a * a - 1)
                coarse = abs(values[a, min(nn)] - reference)
                fine = abs(values[a, max(nn)] - reference)
                # These finest grids resolve truncation below double roundoff.
                # Allow 1e-10 relative error for cancellation near a=1.001.
                self.assertLess(fine / reference, 1e-10, f"Finest-grid reference mismatch: {rel}, {a}")
                # a=2 already converges rapidly on the first grid; the other cases
                # must resolve numerical truncation rather than echo the reference.
                if a != 2.0:
                    self.assertGreater(coarse / reference, 1e-5)
                    self.assertLess(fine, coarse * 1e-5)
                observations[str(a)] = {"reference": reference, "coarse_absolute_error": coarse,
                                        "fine_absolute_error": fine, "fine_relative_error": fine/reference}
            receipt.setdefault("numerics", {})[rel] = observations
            return values

        def suspension(s):
            self.assertTrue(s["cleanup_ok"], "Product did not confirm descendant cleanup")
            remember(s, observe=False)
            observation = {}
            for unit, info in receipt["services"].items():
                props = isolation.service_properties(unit)
                self.assertTrue(props.get("LoadState") == "not-found"
                                or props.get("ActiveState") in ("inactive", "failed"), props)
                groups = {}
                for group in info["groups"]:
                    path = Path("/sys/fs/cgroup") / group.lstrip("/") / "cgroup.events"
                    contents = path.read_text() if path.exists() else "(removed)"
                    self.assertTrue(contents == "(removed)" or "populated 0" in contents, contents)
                    groups[group] = contents
                observation[unit] = {"properties": props, "groups": groups}
            return observation

        def checkpoint(s, name):
            saved = s["checkpoint"]
            self.assertEqual(saved["id"], s["activation_id"])
            handoff = read(saved["handoff"])
            self.assertEqual(hashlib.sha256(handoff.encode()).hexdigest(), saved["handoff_sha256"])
            workspace.validate_handoff(project, handoff)
            read(saved["intake"])
            receipt["phases"][name]["checkpoint"] = saved
            receipt["phases"][name]["handoff"] = handoff
            return handoff

        def indexes():
            # Observe product reconciliation BEFORE the reproduction adds a file.
            directories = [project]
            for name in workspace.MANAGED:
                directories += [p for p in (project / name).rglob("*") if p.is_dir()]
                directories.append(project / name)
            for directory in directories:
                index = (directory / "FOLDER_CONTENT.md").read_text()
                for entry in directory.iterdir():
                    if entry.name != "FOLDER_CONTENT.md":
                        self.assertIn(f"]({quote(entry.name)})", index)
            self.assertFalse(list((project / "starting_evidence").rglob("FOLDER_CONTENT.md")))

        try:
            initial_process = launch(cli("start", "--wall-seconds", "900", "--memory-mib", "2048",
                                         "--max-tasks", "128", "--primary-session-seconds", "240"),
                                     "start", background=True)

            def ready(s):
                drafts = project / session_path(s) / "drafts"
                return (s.get("native_session_id") and s["state"] == "running"
                        and all((drafts / rel).is_file() and (drafts / rel).stat().st_size > 80
                                for rel in ("work/PLAN.md", "work/DERIVATION.md"))
                        and has_json("work/baseline.json") and successful(s, "baseline.json"))

            initial = poll(initial_process, ready, 210, "initial-progress")
            self.assertIsNone(initial_process.poll())
            self.assertTrue(receipt["services"][initial["service"]]["groups"],
                            "Cannot observe active research control group")
            grid = (16, 32, 64, 128, 256, 512)
            rows("work/baseline.json", (1.1, 2.0), grid)
            baseline_hash = workspace.file_digest(project / "work/baseline.json")
            receipt["baseline_sha256"] = baseline_hash
            launch(cli("pause"), "pause-initial", timeout=65)
            self.assertEqual(initial_process.wait(timeout=budget(20)), 0)
            paused = capture("paused", state())
            self.assertEqual(paused["state"], "paused")
            receipt["initial_suspension"] = suspension(paused)
            checkpoint(paused, "paused")
            for rel in ("work/PLAN.md", "work/DERIVATION.md"):
                receipt["phases"]["paused"][rel] = read(rel)
            self.assertEqual(workspace.file_digest(project / "work/baseline.json"), baseline_hash)
            self.assertEqual(workspace.fingerprints(project), expected_inputs)
            self.assertEqual(len(paused["sessions"]), 1)

            questions_file, feedback_file = run / "questions.md", run / "feedback.md"
            questions_file.write_text(REVISED)
            feedback_file.write_text(FEEDBACK)
            launch(cli("redirect", "--questions-file", str(questions_file)), "redirect")
            launch(cli("feedback", "--file", str(feedback_file)), "feedback")
            (project / "AGENTS.md").write_text(NEW_INSTRUCTIONS)
            paragraph = (
                f"Human scientific correction ({run.name}): retain the coarse-grid evidence "
                "when interpreting an apparent error plateau. A flat fine-grid tail alone "
                "cannot establish that truncation is resolved; compare its scale with the "
                "preceding convergence trend before attributing residuals to floating-point effects."
            )
            with (project / "work/DERIVATION.md").open("a") as note:
                note.write("\n\n" + paragraph + "\n")
            receipt["inputs"].update(new_questions=REVISED, new_instructions=NEW_INSTRUCTIONS,
                                     feedback=read("HUMAN_FEEDBACK.md"), human_paragraph=paragraph)
            expected_inputs = workspace.fingerprints(project)
            receipt["expected_input_fingerprints"] = expected_inputs
            edited = capture("human-edited", state())
            self.assertEqual(edited["state"], "paused")
            suspension(edited)
            self.assertEqual(workspace.file_digest(project / "work/baseline.json"), baseline_hash)

            resumed_process = launch(cli("resume"), "resume", background=True)
            resumed = poll(resumed_process,
                           lambda s: s.get("native_session_id") and s["activation_id"] != paused["activation_id"],
                           60, "resumed")
            self.assertNotEqual(resumed["ownership_nonce"], paused["ownership_nonce"])
            pre_id = resumed["activation_id"]
            transition_seen = False

            def rollover(s):
                nonlocal transition_seen
                self.assertIsNone(resumed_process.poll(), "Resume process ended during rollover")
                if s["activation_id"] == pre_id and s.get("rollover", {}).get("phase") == "saving":
                    if not transition_seen:
                        self.assertFalse((project / "work/successor.json").exists(),
                                         "Reserved computation ran before automatic rollover")
                        capture("rollover-saving", s)
                        transition_seen = True
                return (s["activation_id"] != pre_id and s.get("native_session_id")
                        and s.get("rollover", {}).get("phase") == "continued")

            successor = poll(resumed_process, rollover, 300, "automatic-successor")
            self.assertTrue(transition_seen, "No observed automatic saving transition")
            self.assertIsNone(resumed_process.poll())
            self.assertFalse((project / "work/successor.json").exists(),
                             "Reserved computation must be absent at fresh-session transition")
            self.assertEqual(len(successor["sessions"]), 2)
            predecessor = successor["sessions"][-1]
            self.assertEqual(predecessor["activation_id"], pre_id)
            self.assertEqual(predecessor["successor_activation"], successor["activation_id"])
            self.assertEqual(predecessor["outcome"], "rolling_over")
            self.assertTrue(predecessor["cleanup_ok"])
            self.assertEqual(successor["rollover"]["checkpoint_id"], pre_id)
            self.assertEqual(successor["rollover"]["source_activation"], pre_id)
            self.assertEqual(successor["rollover"]["destination_activation"], successor["activation_id"])
            self.assertEqual(successor["rollover"]["predecessor_native_session_id"], resumed["native_session_id"])
            self.assertEqual(predecessor["successor_native_session_id"], successor["native_session_id"])
            self.assertEqual(predecessor["checkpoint_id"], pre_id)
            for key in ("run_id", "logical_researcher_id", "project", "ownership_nonce", "limits",
                        "primary_session_policy"):
                self.assertEqual(successor[key], resumed[key], key)
            self.assertNotEqual(successor["native_session_id"], resumed["native_session_id"])
            prior = session_path(resumed)
            request = json.loads(read(f"{prior}/control/request.json"))
            ack = json.loads(read(f"{prior}/control/ack.json"))
            self.assertEqual(request["reason"], "rollover")
            self.assertTrue(ack["accepted"])
            self.assertTrue(all(ack.get(k) == v for k, v in request.items()))
            self.assertEqual({k: request[k] for k in workspace.owner_fields(resumed)},
                             workspace.owner_fields(resumed))
            prepared = json.loads(read(f"{prior}/prepared.json"))
            self.assertEqual(prepared["owner"], workspace.owner_fields(resumed))
            saved_handoff = read(f"{prior}/prepared-handoff.md")
            self.assertEqual(workspace.file_digest(project / prior / "prepared-handoff.md"),
                             prepared["handoff_sha256"])
            self.assertEqual(saved_handoff, read(successor["checkpoint"]["handoff"]))
            workspace.validate_handoff(project, saved_handoff)
            self.assertIn("1.001", saved_handoff.split("## Next action", 1)[1])
            receipt["rollover_evidence"] = {"request": request, "ack": ack, "prepared": prepared,
                                             "handoff": saved_handoff, "resume_pid": resumed_process.pid}
            rows("work/near.json", (1.01,), grid)
            self.assertTrue(successful(resumed, "near.json"))

            progressed = poll(resumed_process,
                              lambda s: has_json("work/successor.json") and successful(s, "successor.json")
                              and (project / session_path(s) / "drafts/work/CONTINUITY.md").is_file(),
                              210, "successor-progress")
            self.assertEqual(progressed["activation_id"], successor["activation_id"])
            fine_grid = (64, 128, 256, 512, 1024, 2048, 4096)
            original = rows("work/successor.json", (1.001,), fine_grid)
            if resumed_process.poll() is None:
                launch(cli("pause"), "pause-final", timeout=65)
            self.assertEqual(resumed_process.wait(timeout=budget(20)), 0)
            launch(cli("inspect", "--json"), "inspect-json")
            final = capture("final", json.loads((run / "inspect-json.stdout").read_text()))
            self.assertIn(final["state"], ("paused", "completed"))
            receipt["final_suspension"] = suspension(final)
            checkpoint(final, "final")
            self.assertEqual(len(final["sessions"]), 3)
            identities = []
            for summary in final["sessions"]:
                native = summary["native_session_id"]
                self.assertTrue(native)
                identities.append(native)
                self.assertIn(native, [e.get("thread_id") for e in events(summary)
                                       if e.get("type") == "thread.started"])
                self.assertTrue(summary["cleanup_ok"])
                self.assertTrue(summary["service"])
                self.assertTrue(summary["probe_service"])
            self.assertEqual(len(set(identities)), 3)
            for key in ("run_id", "logical_researcher_id", "project", "limits", "primary_session_policy"):
                self.assertEqual(final[key], paused[key], key)
            self.assertEqual(final["ownership_nonce"], resumed["ownership_nonce"])
            for earlier, later in ((paused, successor), (successor, final)):
                self.assertGreater(later["active_seconds"], earlier["active_seconds"])
                self.assertLess(later["remaining_active_seconds"], earlier["remaining_active_seconds"])
            self.assertAlmostEqual(final["active_seconds"] + final["remaining_active_seconds"], 900)
            self.assertAlmostEqual(sum(s["active_seconds"] for s in final["sessions"]), final["active_seconds"])
            totals = {}
            unknown_usage = False
            for summary in final["sessions"]:
                # Verify session summaries against actual completed-turn events.
                observed = {}
                turns = [e for e in events(summary) if e.get("type") == "turn.completed"]
                unknown_usage |= not turns
                for e in turns:
                    usage = e.get("usage")
                    unknown_usage |= (not isinstance(usage, dict) or
                                      any(not isinstance(usage.get(k), int) or isinstance(usage.get(k), bool)
                                          for k in ("input_tokens", "output_tokens")))
                    if isinstance(usage, dict):
                        for key, value in e["usage"].items():
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                observed[key] = observed.get(key, 0) + value
                self.assertEqual(summary["usage_totals"], observed or None)
                for key, value in observed.items():
                    totals[key] = totals.get(key, 0) + value
            self.assertEqual(final["usage_totals"], totals or None)
            receipt["accounting"] = {k: final[k] for k in
                                     ("active_seconds", "remaining_active_seconds", "usage_totals", "usage_complete")}
            if unknown_usage:
                self.assertFalse(final["usage_complete"], "Missing telemetry must remain unknown")
            self.assertEqual(workspace.fingerprints(project), expected_inputs)
            self.assertEqual(workspace.file_digest(project / "work/baseline.json"), baseline_hash)
            preserved = [p for p in [project / "work/DERIVATION.md",
                                     *(project / "handoffs/preserved").rglob("*.md")]
                         if paragraph in p.read_text()]
            self.assertTrue(preserved, "Exact human paragraph was lost")
            receipt["human_preservation"] = [str(p.relative_to(project)) for p in preserved]
            # Structural explanation checks plus new numerical evidence establish
            # adaptation; excerpts below allow controller/manager scientific assessment.
            continuity = read("work/CONTINUITY.md")
            for heading in ("Retained findings", "Revised plan", "Human note and error interpretation"):
                body = continuity.split(f"## {heading}", 1)[-1].split("\n## ", 1)[0].strip()
                self.assertIn(f"## {heading}", continuity)
                self.assertGreater(len(body), 160, f"Missing substantive explanation: {heading}")
            self.assertRegex(continuity.lower(), r"simpson[\s\S]{0,180}(remov|drop|defer|no longer)|"
                             r"(remov|drop|no longer)[\s\S]{0,180}simpson")
            self.assertRegex(continuity.lower(), r"coarse[\s\S]{0,400}(plateau|float|round)")
            for linked in ("baseline.json", "near.json", "DERIVATION.md"):
                self.assertRegex(continuity, r"\]\([^)]*" + re.escape(linked) + r"\)")
            science = continuity + "\n" + read("outputs/REPORT.md")
            for concept in (r"absolute", r"relative", r"1\.01\b", r"1\.001\b"):
                self.assertRegex(science.lower(), concept)
            receipt["scientific_observations"] = {
                "initial_plan": receipt["phases"]["paused"]["work/PLAN.md"][:3500],
                "initial_derivation": receipt["phases"]["paused"]["work/DERIVATION.md"][:3500],
                "continuity": continuity[:10000], "revised_plan": read("work/PLAN.md")[:5000],
                "report": read("outputs/REPORT.md")[:6000],
                "rollover_next_action": saved_handoff.split("## Next action", 1)[1][:3000],
            }
            indexes()
            artifact_hashes = {rel: workspace.file_digest(project / rel) for rel in
                               ("work/baseline.json", "work/near.json", "work/successor.json", "work/compute.py")}
            receipt["artifact_sha256"] = artifact_hashes
            seconds = budget(60)
            reproduction = isolation.Config(wall_seconds=seconds, memory_mib=512, max_tasks=32,
                                             deadline=time.monotonic() + seconds)
            receipt["services"][reproduction.unit] = {"groups": []}
            argv = ["/usr/bin/python3", "/project/work/compute.py", "--a", "1.001", "--n",
                    *map(str, fine_grid), "--output", "/project/work/reproduced.json"]
            receipt["reproduction_invocation"] = {"api": "research_pipeline.isolation.run_isolated",
                                                  "config": asdict(reproduction), "argv": argv}
            rerun = (
                "from pathlib import Path; import time; from research_pipeline import isolation; "
                "c = isolation.Config(wall_seconds=60, memory_mib=512, max_tasks=32, "
                "deadline=time.monotonic()+60); "
                f"r = isolation.run_isolated(c, Path({str(project)!r}), {argv!r}); "
                "print(r); raise SystemExit(r.returncode if r.cleanup_ok else 4)")
            receipt["reproduction_rerun_command"] = shlex.join([sys.executable, "-c", rerun])
            with (run / "reproduce.stdout").open("wb") as out, (run / "reproduce.stderr").open("wb") as err:
                def record(channel, data):
                    stream = out if channel == "stdout" else err
                    stream.write(data[:max(0, 4 * 1024 * 1024 - stream.tell())])
                result = isolation.run_isolated(reproduction, project, argv, on_event=record)
            receipt["reproduction"] = asdict(result)
            group = result.service_properties.get("ControlGroup")
            if group:
                receipt["services"][reproduction.unit]["groups"].append(group)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(result.cleanup_ok)
            reproduced = rows("work/reproduced.json", (1.001,), fine_grid)
            for key, value in original.items():
                self.assertTrue(math.isclose(value, reproduced[key], rel_tol=1e-12, abs_tol=1e-12))
            for rel, digest in artifact_hashes.items():
                self.assertEqual(workspace.file_digest(project / rel), digest)
            receipt["checks_passed"] = True
        except BaseException as exc:
            primary_error = exc
            receipt["failure"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            cleanup_errors = []
            # Prevent further launches BEFORE gathering latest service identities.
            for process, record in processes:
                try:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=budget(25, cleanup=True))
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=budget(5, cleanup=True))
                    record["returncode"] = process.returncode
                except BaseException as exc:
                    cleanup_errors.append(f"foreground cleanup: {exc}")
            try:
                if (project / ".research_pipeline/run.json").exists():
                    latest = state()
                    receipt["last_state"] = latest
                    remember(latest, observe=False)
            except BaseException as exc:
                cleanup_errors.append(f"collect durable services: {exc}")
            for unit in receipt["services"]:
                try:
                    budget(1, cleanup=True)
                    stopped = isolation.stop_service(unit)
                    receipt["cleanup"][unit] = {"confirmed": stopped}
                    if not stopped:
                        cleanup_errors.append(f"Unconfirmed service cleanup: {unit}")
                except BaseException as exc:
                    cleanup_errors.append(f"{unit}: {exc}")
            try:
                self.assertEqual(workspace.fingerprints(project), expected_inputs)
                self.assertFalse(list((project / "starting_evidence").rglob("FOLDER_CONTENT.md")))
                if not cleanup_errors and receipt.get("last_state", {}).get("cleanup_ok"):
                    receipt["cleanup_observation"] = suspension(receipt["last_state"])
                    workspace.refresh_indexes(project)
                budget(1, cleanup=True)
            except BaseException as exc:
                cleanup_errors.append(f"final integrity/cleanup: {exc}")
            receipt["cleanup_errors"] = cleanup_errors
            receipt["elapsed_seconds"] = time.monotonic() - began
            if receipt.get("checks_passed") and not cleanup_errors and primary_error is None:
                receipt["outcome"] = "passed"
            (run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(f"M2 outcome: {receipt['outcome']}; receipt: {run / 'receipt.json'}", flush=True)
            for label, observation in receipt.get("scientific_observations", {}).items():
                print(f"\nM2 {label}:\n{observation}", flush=True)
            print("M2 numerical observations: " + json.dumps(receipt.get("numerics", {})), flush=True)
            print("M2 cumulative accounting: " + json.dumps(receipt.get("accounting", {})), flush=True)
            print("M2 preserved human edits: " + json.dumps(receipt.get("human_preservation", [])), flush=True)
            print("M2 cleanup: " + json.dumps(receipt["cleanup"]), flush=True)
            if cleanup_errors and primary_error is None:
                self.fail("; ".join(cleanup_errors))
