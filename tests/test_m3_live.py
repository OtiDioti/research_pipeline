"""Opt-in bounded M3 science: real Codex roles, production coordination/isolation."""
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import quote

from tests import use_checkout

use_checkout()
from research_pipeline import codex, isolation, verification, workspace


QUESTIONS = """# Near-boundary approximation and independent challenge
Investigate I(a) = integral from 0 to 2*pi of 1/(a-cos(theta)) dtheta, a>1.
Derive the leading near-boundary approximation and its next correction separately,
assess a candidate ONE PERCENT validity regime for the leading approximation,
and distinguish approximation error, discretization error and floating-point uncertainty.
Treat broad applicability as a hypothesis, never assert an unsupported bound as fact.

This is a SMALL bounded demonstration. Prioritize the dependent calculation, safe
handoff, integration and independent challenge over optional surveys, plots or extra
precision programs. Keep notes and packets concise and self-contained. One useful
convergence analysis and one numerical sensitivity/roundoff check suffice for the
dependent task; disclose any remaining uncertainty. Do not spend the session filling
the time with increasingly expensive grids. Keep handoffs current from the first
calculation; when saving is requested, acknowledge the existing useful work promptly.
Combine the checkpoint --check with each scientific shell command where practical.
After the reserved successor calculation and its compact uncertainty assessment,
deliver RESULT.md promptly so primary can integrate and start independent checking.

PRIMARY: delegate exactly ONE dependent quadrature/convergence study, with a scientific
benefit: you need independently computed numerical evidence while you derive the
analytical approximation and its correction. Use the primary helper --delegate. The
assignment must carry the following staged calculation/interface requirements.

DELEGATED RESEARCHER (only): author standard-library compute.py in YOUR assigned
workspace, accepting --a (parameter list), --n (grid list), --output (JSON path).
Save {"rows": [{"a": ..., "n": ..., "estimate": ...}, ...]} with actual periodic
trapezoidal sums, never an analytical formula substituted for numerical quadrature.
Before automatic rollover calculate a=1.01, n=16,32,64,128,256,512,1024 in baseline.json.
Preserve its bytes and compute.py unchanged on continuation. Continue useful convergence/error/sensitivity
analysis, keeping an intelligible handoff saved EARLY. Reserve a=1.001 for your
AUTOMATIC SUCCESSOR: its concrete Next action must use saved compute.py to calculate
n=16,32,64,128,256,512,1024,2048,4096 in successor.json and extend the uncertainty
assessment. Do not do this reserved calculation in the first context. Do not finish
before the requested automatic handoff while meaningful numerical analysis remains.
Check the checkpoint helper after commands; acknowledge promptly when asked. The
fresh successor continues this same task, writes RESULT.md with links to code/data
and limitations, and finishes. Do not repeat the saved baseline on continuation.

PRIMARY: while that task runs and rolls over, continue substantive analytical and
computational work. Author work/parent.py accepting --output, save work/parent.json
as {"rows": [{"a": ..., "approximation": ..., "reference": ..., "relative_error": ...}]}
for an expanding parameter study of YOUR derived approximation. Use distinct a>1
parameters and actual calculations; relative_error is an absolute fraction, not a
percentage, against your accurately derived reference. Save work/PARENT.md with the evolving
error argument. Extend this study during the child handoff and successor calculation,
so the saved rows and derivation show useful parent progress across the transition.
No sleep/heartbeat/poll loop as a substitute for science. Consult sources and report
access honestly. Save required plan, literature, status, report and handoff drafts.
Stage the parent study in small useful expansions, retaining new parameters for the
observed child saving/continuation interval; do not exhaust all extensions beforehand.
Once the child delivers, prioritize integration and verification over optional analyses.

After the child delivers, integrate its numerical findings and uncertainties into
the parent approximation analysis. Request exactly ONE separate independent verifier
using --verify, with scientific parent primary. The packet's Claim and scope must
include TWO distinct subjects: your derived near-boundary validity regime, and the
exploratory hypothesis that the leading approximation's one-percent accuracy extends
across the parameter study, including a=1.2. Submit the latter as a hypothesis to test,
never an established bound, even if your own calculations already argue against it.
Supply assumptions, sources and reproducible artifacts. Ask for independent reasoning
and independently authored checks of both subjects; do not restrict the examination
to confirming your narrowed theorem or exclude broader applicability from its scope.
Do not manufacture a false claim or prescribe the verdict. The packet must EXPLICITLY
link every local Markdown dependency recursively (including code/data linked from
notes), within the existing packet limits. A short self-contained claim note can
avoid irrelevant links.
Never supply conversations. Include these verification interface requirements:

VERIFIER (only): independently author check.py in YOUR workspace, accepting --output
and writing {"rows": [{"a": ..., "reference": ..., "approximation": ...,
"relative_error": ...}]} including a=1.2 and near-boundary cases. Use your own
reconstruction, preferably another method; relative_error is an absolute fraction,
not a percentage. Execute it and explain whether the stress
observations challenge the proposed approximation/regime or an unsupported extension.
Address BOTH the scoped near-boundary result and the submitted broader applicability
hypothesis. If your evidence rejects that hypothesis, record a substantive objection
to that extension, distinguishing it from any theorem you confirm. An objection need
not allege that the researcher asserted a false theorem: an independently refuted
exploratory hypothesis also needs a documented response and scope decision. Do not
invent disagreement if the evidence supports both subjects; report your actual verdict.
Write substantive CHECK.md linking the independent check code/data and frozen evidence.
A substantive objection should identify the scientific issue, numerical observations,
and a justified targeted test if useful. Finish this examination rather than waiting.
On re-examination preserve ALL initial reports and linked code/data/notes; use NEW
paths for any revised checks. Respond independently to the accepted response/version,
perform a justified targeted test, saving NEW JSON with the same row interface and
the stress case a=1.2, and link its code/data in REEXAMINATION.md. You may rerun
unchanged check.py with a new output path or author a revised check. Finish. Remaining
opposing arguments are disputed after this finite exchange; do not force consensus.

PRIMARY: read the independent check. If challenged, write one scientific response
with correction, qualification, opposing argument or a justified targeted test; submit
--respond with --response. Include every local dependency explicitly. Read the final
check, preserve unresolved arguments, and finish. Do not create extra verifiers or
exchange rounds to obtain agreement. Synthesis must link the delegated RESULT.md,
CHECK.md, accepted frozen response packet and REEXAMINATION.md, and explain scope,
assumptions, uncertainty, objection, superseded conclusions and the final checked or
disputed outcome, including the a=1.2 numerical observation. Use relative canonical
Markdown links in outputs/REPORT.md. Do not finish while tasks are unfinished.
"""


def parent_overlap(progress, milestones):
    """Require new science between observed saving and successor calculation."""
    start = milestones["saving"]["elapsed"]
    end = milestones["continued_calculation"]["elapsed"]
    observations = [p for p in progress if start <= p["elapsed"] <= end]
    if len(observations) < 2:
        raise AssertionError("Missing substantive parent progress during child transition")
    before, after = observations[0], observations[-1]
    if not {r["a"] for r in after["rows"]} - {r["a"] for r in before["rows"]}:
        raise AssertionError("Parent did not extend its parameter study during child rollover")
    prior_commands = (len(before["commands"]) if
                      before["native_session_id"] == after["native_session_id"] else 0)
    if len(after["commands"]) <= prior_commands:
        raise AssertionError("No new parent calculation event during transition")
    return before, after


def reproduction_driver(invocations):
    """Run each saved program from its original task workspace inside isolation."""
    return "import subprocess; " + "; ".join(
        f"subprocess.run({item['argv']!r}, cwd={item['cwd']!r}, check=True, timeout=25)"
        for item in invocations)


def check_synthesis(project, report, result, record):
    """Check linked outcomes; scientific prose need not use a fixed vocabulary."""
    for rel in (result, record["initial_check"], record["response"]["packet"], record["final_check"]):
        if not any(verification.link_path(project, "outputs/REPORT.md", target) == rel
                   for target in verification.LINK.findall(report)):
            raise AssertionError(f"Synthesis missing {rel}")
    if record["disposition"] not in report.lower():
        raise AssertionError(f"Synthesis missing {record['disposition']}")
    if not re.search(r"1\.2\b", report):
        raise AssertionError("Synthesis must address the observed stress case a=1.2")


@unittest.skipUnless(os.environ.get("RESEARCH_PIPELINE_M3_LIVE") == "1",
                     "Live M3 requires explicit RESEARCH_PIPELINE_M3_LIVE=1; no inference started")
class LiveM3Acceptance(unittest.TestCase):
    def test_real_delegation_rollover_independent_challenge_and_integration(self):
        output = os.environ.get("RESEARCH_PIPELINE_M3_OUTPUT_DIR")
        self.assertTrue(output, "Enabled live M3 requires RESEARCH_PIPELINE_M3_OUTPUT_DIR")
        began = time.monotonic()
        deadline, work_deadline = began + 1800, began + 1200
        base = Path(output).absolute()
        base.mkdir(parents=True, exist_ok=True)
        run = Path(tempfile.mkdtemp(prefix="m3-live-", dir=base))
        run.chmod(0o700)
        project = run / "project"
        (project / "starting_evidence").mkdir(parents=True)
        (project / "starting_evidence/RESEARCH_QUESTIONS.md").write_text(QUESTIONS)
        (project / "AGENTS.md").write_text(
            "Use deterministic standard-library Python calculations, useful Markdown and honest uncertainty.\n")
        inputs = workspace.fingerprints(project)
        receipt = {"invocation": run.name, "project": str(project), "started_at": time.time(),
                   "bounds_seconds": {"active": 900, "primary_session": 540,
                                      "delegated_session": 240, "reproduction": 60,
                                      "ordinary_cutoff": 1200, "whole": 1800},
                   "commands": [], "services": {}, "milestones": {}, "parent_progress": [],
                   "limitations": codex.LIMITATIONS, "outcome": "failed"}
        processes, latest, baseline_hash, child_before = [], None, None, None
        baseline_code_hash = None
        failure = None
        print(f"\nM3 private acceptance artifacts: {run}", flush=True)

        def remaining(cleanup=False):
            value = (deadline if cleanup else work_deadline) - time.monotonic()
            self.assertGreater(value, 0, "M3 outer deadline exhausted")
            return value

        def read(rel):
            path = workspace.safe_path(project, rel)
            self.assertTrue(path.is_file(), f"Missing regular scientific evidence: {rel}")
            self.assertLessEqual(path.stat().st_size, 4 * 1024 * 1024, rel)
            return path.read_text()

        def load_state():
            return json.loads(read(".research_pipeline/run.json"))

        def session(entry):
            return f".research_pipeline/sessions/{entry['activation_id']}"

        def entries(s):
            return [*s.get("sessions", []),
                    *(t["activation"] for t in s.get("tasks", {}).values() if t.get("activation"))]

        def remember(s, observe=False):
            for entry in entries(s):
                for key, flag in (("service", "service_attempted"), ("probe_service", "probe_attempted")):
                    unit = entry.get(key)
                    if not unit or not entry.get(flag):
                        continue
                    info = receipt["services"].setdefault(unit, {"groups": []})
                    props = entry.get("execution", {}).get("service_properties", {})
                    if observe and not info.get("observed"):
                        props = isolation.service_properties(unit, deadline=work_deadline)
                        if props.get("LoadState") != "not-found":
                            info["observed"] = props
                    group = props.get("ControlGroup")
                    if group and group not in info["groups"]:
                        info["groups"].append(group)

        def events(entry):
            path = project / session(entry) / "backend.jsonl"
            if not path.exists():
                return []
            result = []
            for line in read(str(path.relative_to(project))).splitlines():
                try:
                    result.append(json.loads(line))
                except ValueError:
                    pass  # The current final event may be incomplete.
            return result

        def commands(entry, needle=""):
            return [e["item"]["command"] for e in events(entry)
                    if e.get("type") == "item.completed"
                    and e.get("item", {}).get("type") == "command_execution"
                    and e["item"].get("exit_code") == 0
                    and needle in e["item"].get("command", "")]

        def milestone(name, value):
            if name not in receipt["milestones"]:
                receipt["milestones"][name] = {"elapsed": time.monotonic() - began, **value}

        def launch(argv, name):
            record = {"argv": argv, "command": shlex.join(argv),
                      "stdout": str(run / f"{name}.stdout"), "stderr": str(run / f"{name}.stderr")}
            receipt["commands"].append(record)
            print(f"M3 command: {record['command']}", flush=True)
            with open(record["stdout"], "wb") as out, open(record["stderr"], "wb") as err:
                process = subprocess.Popen(argv, stdout=out, stderr=err)
            processes.append((process, record))
            return process

        def stopped(s, cleanup=False):
            if not cleanup:
                self.assertTrue(s["cleanup_ok"], "Product did not confirm cleanup")
            remember(s)
            observations = {}
            for unit, info in receipt["services"].items():
                remaining(cleanup)
                props = isolation.service_properties(unit, deadline=deadline if cleanup else work_deadline)
                self.assertTrue(props.get("LoadState") == "not-found"
                                or props.get("ActiveState") in ("inactive", "failed"), props)
                groups = {}
                for group in info["groups"]:
                    path = Path("/sys/fs/cgroup") / group.lstrip("/") / "cgroup.events"
                    contents = path.read_text() if path.exists() else "(removed)"
                    self.assertTrue(contents == "(removed)" or "populated 0" in contents, contents)
                    groups[group] = contents
                observations[unit] = {"properties": props, "groups": groups}
            return observations

        def quadrature(rel, a, grids):
            rows = json.loads(read(rel))["rows"]
            self.assertEqual(len(rows), len(grids))
            values = {}
            for row in rows:
                self.assertEqual(row["a"], a)
                self.assertIn(row["n"], grids)
                self.assertNotIn(row["n"], values)
                self.assertTrue(math.isfinite(row["estimate"]) and row["estimate"] > 0)
                values[row["n"]] = row["estimate"]
            reference = 2 * math.pi / math.sqrt((a - 1) * (a + 1))
            errors = {n: abs(v / reference - 1) for n, v in values.items()}
            self.assertGreater(errors[min(grids)], 1e-5, "Coarse row must be actual unresolved quadrature")
            self.assertLess(errors[max(grids)], 1e-10)
            self.assertLess(errors[max(grids)], errors[min(grids)] * 1e-5)
            receipt.setdefault("numerics", {})[rel] = {"reference": reference, "relative_errors": errors}
            return values

        def check_observations(rel, challenge=True):
            rows = json.loads(read(rel))["rows"]
            self.assertGreaterEqual(len(rows), 2)
            seen, stress = set(), None
            for row in rows:
                a = row["a"]
                self.assertGreater(a, 1)
                self.assertNotIn(a, seen)
                seen.add(a)
                self.assertTrue(all(math.isfinite(row[k]) for k in
                                    ("reference", "approximation", "relative_error")))
                reference = 2 * math.pi / math.sqrt((a - 1) * (a + 1))
                self.assertTrue(math.isclose(row["reference"], reference, rel_tol=1e-8))
                error = abs(row["approximation"] / row["reference"] - 1)
                self.assertAlmostEqual(row["relative_error"], error, delta=1e-8)
                if math.isclose(a, 1.2, abs_tol=1e-12):
                    stress = row
            self.assertIsNotNone(stress, "Independent stress observation absent")
            if challenge:
                self.assertGreater(stress["relative_error"], .01,
                                   "Stress observation does not substantiate required one-percent challenge")
            receipt.setdefault("numerics", {})[rel] = rows
            return rows

        try:
            self.assertNotEqual(os.environ.get("RESEARCH_PIPELINE_M1_LIVE"), "1", "Leave M1 paid gate disabled")
            self.assertNotEqual(os.environ.get("RESEARCH_PIPELINE_M2_LIVE"), "1", "Leave M2 paid gate disabled")
            owner = launch([sys.executable, "-m", "research_pipeline", "start", str(project),
                            "--wall-seconds", "900", "--max-agents", "2", "--memory-mib", "2048",
                            "--max-tasks", "128", "--primary-session-seconds", "540",
                            "--delegated-session-seconds", "240"], "start")
            while True:
                remaining()
                if (project / ".research_pipeline/run.json").exists():
                    latest = load_state()
                    remember(latest, observe=True)
                    tasks = latest["tasks"]
                    all_entries = {e["activation_id"]: e for e in entries(latest)}
                    counts = {}
                    for t in tasks.values():
                        count = len({e["activation_id"] for e in latest["sessions"] if e["task_id"] == t["task_id"]}
                                    | ({t["activation"]["activation_id"]} if t.get("activation") else set()))
                        counts[t["task_id"]] = count
                        self.assertLessEqual(count, 2, "Unexpected activation; no automatic paid retry allowed")
                    children = [t for t in tasks.values() if t["role"] == "researcher"]
                    verifiers = [t for t in tasks.values() if t["role"] == "verifier"]
                    self.assertLessEqual(len(children), 1)
                    self.assertLessEqual(len(verifiers), 1)
                    if children:
                        child = children[0]
                        act, root = child.get("activation"), child["workspace"]
                        if act and act.get("native_session_id"):
                            milestone("delegated", {"task": json.loads(json.dumps(child)), "state": latest})
                            if child_before is None:
                                child_before = json.loads(json.dumps(child))
                        baseline = project / root / "baseline.json"
                        if baseline.is_file() and baseline_hash is None and commands(act, "baseline.json"):
                            baseline_hash = workspace.file_digest(baseline)
                            baseline_code_hash = workspace.file_digest(project / root / "compute.py")
                            self.assertTrue(baseline_code_hash)
                            self.assertFalse((project / root / "successor.json").exists())
                            milestone("baseline", {"sha256": baseline_hash, "code_sha256": baseline_code_hash})
                        predecessor_id = child_before["activation"]["activation_id"] if child_before else None
                        if predecessor_id:
                            prior = all_entries[predecessor_id]
                            prior_session = session(prior)
                            request = workspace.read_control(project / prior_session / "control/request.json")
                            ack = workspace.read_control(project / prior_session / "control/ack.json")
                            if request and request["reason"] == "rollover":
                                milestone("saving", {"request": request})
                            if ack and ack.get("accepted"):
                                milestone("acknowledged", {"ack": ack, "prepared": json.loads(read(prior_session + "/prepared.json")),
                                                          "handoff": read(prior_session + "/prepared-handoff.md")})
                            if act and act["activation_id"] != predecessor_id and act.get("native_session_id"):
                                milestone("successor", {"task": json.loads(json.dumps(child)), "state": latest})
                            # Anchor the window to actual saving, not a predicted deadline.
                            # Take the final snapshot before recording observed continuation.
                            if ("saving" in receipt["milestones"]
                                    and "continued_calculation" not in receipt["milestones"]):
                                primary = tasks["primary"]["activation"]
                                note = project / session(primary) / "drafts/work/PARENT.md"
                                data = project / "work/parent.json"
                                if note.is_file() and data.is_file():
                                    try:
                                        observations = json.loads(read("work/parent.json"))["rows"]
                                    except ValueError:
                                        observations = []
                                    signature = hashlib.sha256(data.read_bytes()).hexdigest()
                                    progress = receipt["parent_progress"]
                                    if observations and (not progress or progress[-1]["sha256"] != signature):
                                        progress.append({"elapsed": time.monotonic() - began,
                                            "native_session_id": primary.get("native_session_id"),
                                            "child_activation": act["activation_id"], "sha256": signature,
                                            "rows": observations, "derivation": note.read_text()[:3500],
                                            "commands": commands(primary, "parent")})
                                    elif observations and progress[-1]["native_session_id"] == primary.get("native_session_id"):
                                        # A command can finish just after its output was observed.
                                        progress[-1]["commands"] = commands(primary, "parent")
                            if act and act["activation_id"] != predecessor_id and act.get("native_session_id"):
                                continued_commands = commands(act, "successor.json")
                                if continued_commands:
                                    milestone("continued_calculation", {"commands": continued_commands})
                    for verifier in verifiers:
                        record = verifier["verification"]
                        if record.get("initial_check"):
                            milestone("independent_check", {"verification": json.loads(json.dumps(record)),
                                                          "text": read(record["initial_check"])})
                        if record.get("response_committed"):
                            milestone("response", {"verification": json.loads(json.dumps(record)),
                                                  "text": read(record["response"]["packet"])})
                if owner.poll() is not None:
                    break
                time.sleep(.2)
            diagnostic = (latest["tasks"]["primary"].get("checkpoint_error") or latest.get("reason")) if latest else str(run)
            self.assertEqual(owner.wait(timeout=min(5, remaining())), 0, diagnostic)
            final = load_state()
            receipt["final_state"] = final
            self.assertEqual(final["state"], "completed", final.get("validation_failures"))
            # Observe normal shutdown BEFORE emergency cleanup could hide a failure.
            receipt["normal_cleanup"] = stopped(final)
            with workspace.acquire_project_lock(project):
                receipt["foreground_lock_released"] = True
            self.assertEqual(workspace.fingerprints(project), inputs)
            self.assertEqual(final["limits"], {"wall_seconds": 900, "memory_mib": 2048, "swap_bytes": 0,
                "max_tasks": 128, "per_file_bytes": 67108864, "log_bytes_per_stream": 4194304,
                "concurrent_researchers": 2})
            self.assertEqual(final["capabilities"]["slot_limits"], {"memory_mib": 1024, "max_tasks": 64, "swap_bytes": 0})
            self.assertEqual(final["primary_session_policy"]["session_seconds"], 540)
            self.assertEqual(final["delegated_session_policy"]["session_seconds"], 240)
            self.assertEqual(len(final["tasks"]), 3)
            receipt["backend_argv"] = {task["task_id"]: codex.build_command(isolation.Config(
                codex=final["backend"]["executable"], task_id=task["task_id"]))
                for task in final["tasks"].values()}
            child = next(t for t in final["tasks"].values() if t["role"] == "researcher")
            verifier = next(t for t in final["tasks"].values() if t["role"] == "verifier")
            child_sessions = [s for s in final["sessions"] if s["task_id"] == child["task_id"]]
            verifier_sessions = [s for s in final["sessions"] if s["task_id"] == verifier["task_id"]]
            self.assertIn("Disposition: objection", read(verifier["verification"]["initial_check"]),
                          "Initial verifier found no objection: the required scientific exchange "
                          "was not demonstrated; inspect the frozen packet scope and CHECK.md")
            self.assertEqual(len(child_sessions), 2)
            self.assertEqual(len(verifier_sessions), 2)
            self.assertLessEqual(len(final["sessions"]), 6)
            natives = []
            totals, unknown = {}, False
            for s in final["sessions"]:
                self.assertTrue(s["cleanup_ok"])
                self.assertTrue(s["native_session_id"])
                natives.append(s["native_session_id"])
                self.assertIn(s["native_session_id"], [e.get("thread_id") for e in events(s) if e.get("type") == "thread.started"])
                self.assertLessEqual(s["session_deadline_monotonic"] - s["started_monotonic"], 600)
                turns = [e for e in events(s) if e.get("type") == "turn.completed"]
                observed = {}
                unknown |= not turns
                for e in turns:
                    usage = e.get("usage")
                    unknown |= not isinstance(usage, dict) or any(type((usage or {}).get(k)) is not int for k in ("input_tokens", "output_tokens"))
                    for k, v in (usage if isinstance(usage, dict) else {}).items():
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            observed[k] = observed.get(k, 0) + v
                            totals[k] = totals.get(k, 0) + v
                self.assertEqual(s["usage_totals"], observed or None)
                receipt.setdefault("scientific_commands", {})[s["activation_id"]] = commands(s)
            self.assertEqual(len(set(natives)), len(natives))
            self.assertEqual(final["usage_totals"], totals or None)
            if unknown:
                self.assertFalse(final["usage_complete"])
            self.assertAlmostEqual(final["active_seconds"] + final["remaining_active_seconds"], 900)
            receipt["accounting"] = {k: final[k] for k in ("limits", "active_seconds", "remaining_active_seconds", "usage_totals", "usage_complete")}
            before, after = child_sessions
            self.assertEqual(before["outcome"], "rolling_over")
            self.assertEqual(before["successor_activation"], after["activation_id"])
            self.assertEqual(after["predecessor_activation"], before["activation_id"])
            self.assertEqual(before["checkpoint_id"], before["activation_id"])
            self.assertNotEqual(before["service"], after["service"])
            for name in ("delegated", "baseline", "saving", "acknowledged", "successor", "continued_calculation", "independent_check", "response"):
                self.assertIn(name, receipt["milestones"], f"Missing live milestone: {name}")
            continued = receipt["milestones"]["successor"]
            for key in ("task_id", "logical_researcher_id", "objective", "parent_task", "assigning_primary", "workspace"):
                self.assertEqual(child_before[key], child[key])
                self.assertEqual(child_before[key], continued["task"][key])
            earlier_state = receipt["milestones"]["delegated"]["state"]
            for key in ("run_id", "ownership_nonce", "limits"):
                self.assertEqual(earlier_state[key], continued["state"][key])
            self.assertGreater(continued["state"]["active_seconds"], earlier_state["active_seconds"])
            self.assertGreater(final["active_seconds"], continued["state"]["active_seconds"])
            prepared = receipt["milestones"]["acknowledged"]
            ack, request = prepared["ack"], receipt["milestones"]["saving"]["request"]
            self.assertTrue(all(ack.get(k) == v for k, v in request.items()))
            self.assertEqual(prepared["prepared"]["owner"],
                             {**workspace.owner_fields(final), "activation_id": before["activation_id"]})
            self.assertEqual(hashlib.sha256(prepared["handoff"].encode()).hexdigest(), prepared["prepared"]["handoff_sha256"])
            workspace.validate_handoff(project, prepared["handoff"], task_id=child["task_id"])
            next_action = verification.sections(prepared["handoff"], ("Next action",))["Next action"]
            self.assertIn("1.001", next_action)
            root = child["workspace"]
            self.assertEqual(workspace.file_digest(project / root / "baseline.json"), baseline_hash)
            self.assertEqual(workspace.file_digest(project / root / "compute.py"), baseline_code_hash)
            quadrature(root + "/baseline.json", 1.01, (16,32,64,128,256,512,1024))
            successor_values = quadrature(root + "/successor.json", 1.001, (16,32,64,128,256,512,1024,2048,4096))
            self.assertTrue(commands(after, "successor.json"))
            progress = parent_overlap(receipt["parent_progress"], receipt["milestones"])
            receipt["parent_overlap"] = {
                "start_elapsed": receipt["milestones"]["saving"]["elapsed"],
                "end_elapsed": receipt["milestones"]["continued_calculation"]["elapsed"],
                "before": progress[0], "after": progress[-1]}
            for observation in progress:
                self.assertTrue(observation["native_session_id"])
                for row in observation["rows"]:
                    self.assertGreater(row["a"], 1)
                    self.assertTrue(all(math.isfinite(row[k]) for k in ("approximation", "reference", "relative_error")))
                    reference = 2 * math.pi / math.sqrt((row["a"] - 1) * (row["a"] + 1))
                    self.assertTrue(math.isclose(row["reference"], reference, rel_tol=1e-8))
                    self.assertAlmostEqual(row["relative_error"], abs(row["approximation"] / reference - 1), delta=1e-8)
            self.assertGreater(len(progress[-1]["derivation"]), 100)
            record = verifier["verification"]
            verification.check_unchanged(project, verifier, work_deadline)
            self.assertEqual(record["phase"], "closed")
            self.assertEqual(record["exchange_limit"], 1)
            self.assertTrue(record["response_committed"])
            self.assertIn(record["disposition"], ("checked", "disputed"))
            self.assertEqual(record["reviewed_version"], record["response"]["version"])
            initial_check, final_check = read(record["initial_check"]), read(record["final_check"])
            for text in (initial_check, read(record["response"]["packet"]), final_check):
                self.assertRegex(text, r"1\.2\b", "Exchange must address the observed stress case")
            independent = verifier["workspace"]
            # The check report supplies its data path; do not assume a model-chosen filename.
            linked = record["initial_check_artifacts"]
            check_data = [rel for rel in linked if rel.startswith(independent + "/") and rel.endswith(".json") and "/inputs/" not in rel]
            self.assertEqual(len(check_data), 1, "Initial check must link one independent numerical observation file")
            original_check = check_observations(check_data[0])
            self.assertIn(independent + "/check.py", linked)
            self.assertTrue(commands(verifier_sessions[0], "check.py"))
            final_artifacts = record["final_check_artifacts"]
            targeted = [rel for rel in final_artifacts if rel.startswith(independent + "/")
                        and rel.endswith(".json") and "/inputs/" not in rel and rel not in linked]
            self.assertEqual(len(targeted), 1, "Re-examination must link a new targeted numerical observation")
            check_observations(targeted[0], challenge=False)
            check_code = [rel for rel in final_artifacts if rel.startswith(independent + "/")
                          and rel.endswith(".py") and "/inputs/" not in rel]
            self.assertTrue(any("python" in command and Path(rel).name in command
                                and Path(targeted[0]).name in command
                                for rel in check_code for command in commands(verifier_sessions[1])),
                            "No executed targeted calculation attributable to re-examination")
            for t in (child, verifier):
                self.assertTrue(t["integration"])
            report = read("outputs/REPORT.md")
            check_synthesis(project, report, child["delivery"]["result"], record)
            receipt["scientific_excerpts"] = {"assignment_benefit": child["scientific_benefit"],
                "handoff_next_action": next_action, "successor_findings": read(child["delivery"]["result"])[:5000],
                "parent_progress": progress[-1]["derivation"], "verifier_objection": initial_check[:5000],
                "response": read(record["response"]["packet"])[:5000], "final_check": final_check[:5000], "synthesis": report[:7000]}
            self.assertFalse(list((project / "starting_evidence").rglob("FOLDER_CONTENT.md")))
            # Check product indexes before reproduction intentionally adds outputs.
            directories = [project]
            for name in workspace.MANAGED:
                directories.extend([project / name, *((project / name).rglob("*"))])
            for directory in directories:
                if directory.is_dir() and not directory.is_symlink():
                    index = (directory / "FOLDER_CONTENT.md").read_text()
                    for entry in directory.iterdir():
                        if entry.name != "FOLDER_CONTENT.md":
                            self.assertIn(f"]({quote(entry.name)})", index)
            # Reproduce in the production isolation service, never on this controller host.
            seconds = min(60, remaining())
            reproduction = isolation.Config(wall_seconds=seconds, memory_mib=512, max_tasks=32,
                                             deadline=time.monotonic() + seconds)
            receipt["services"][reproduction.unit] = {"groups": []}
            argv1 = ["/usr/bin/python3", "/project/" + root + "/compute.py", "--a", "1.001", "--n",
                     *map(str, (16,32,64,128,256,512,1024,2048,4096)), "--output", "/project/work/reproduced-child.json"]
            argv2 = ["/usr/bin/python3", "/project/" + independent + "/check.py", "--output", "/project/work/reproduced-check.json"]
            invocations = [{"argv": argv1, "cwd": "/project/" + root},
                           {"argv": argv2, "cwd": "/project/" + independent}]
            argv = ["/usr/bin/python3", "-c", reproduction_driver(invocations)]
            receipt["reproduction_invocation"] = {"api": "research_pipeline.isolation.run_isolated", "argv": argv,
                                                   "scientific_commands": invocations, "config": asdict(reproduction)}
            with (run / "reproduce.stdout").open("wb") as out, (run / "reproduce.stderr").open("wb") as err:
                def capture(channel, data):
                    stream = out if channel == "stdout" else err
                    stream.write(data[:max(0, 4*1024*1024 - stream.tell())])
                result = isolation.run_isolated(reproduction, project, argv, on_event=capture)
            receipt["reproduction"] = asdict(result)
            group = result.service_properties.get("ControlGroup")
            if group:
                receipt["services"][reproduction.unit]["groups"].append(group)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(result.cleanup_ok)
            repeated = quadrature("work/reproduced-child.json", 1.001, (16,32,64,128,256,512,1024,2048,4096))
            for n, value in successor_values.items():
                self.assertTrue(math.isclose(value, repeated[n], rel_tol=1e-12, abs_tol=1e-12))
            self.assertEqual(check_observations("work/reproduced-check.json"), original_check)
            self.assertEqual(workspace.file_digest(project / root / "baseline.json"), baseline_hash)
            self.assertEqual(workspace.file_digest(project / root / "compute.py"), baseline_code_hash)
            verification.check_unchanged(project, verifier, work_deadline)
            receipt["reproduction_cleanup"] = stopped(final)
            receipt["checks_passed"] = True
        except BaseException as exc:
            failure = exc
            receipt["failure"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            cleanup_errors = []
            # Stop the foreground owner before inventorying all attempted units.
            for process, command in processes:
                try:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=min(25, remaining(True)))
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=min(5, remaining(True)))
                    command["returncode"] = process.returncode
                except BaseException as exc:
                    cleanup_errors.append(f"foreground: {exc}")
            try:
                if (project / ".research_pipeline/run.json").exists():
                    latest = load_state()
                    receipt["last_state"] = latest
                    remember(latest)
            except BaseException as exc:
                cleanup_errors.append(f"service inventory: {exc}")
            receipt["cleanup"] = {}
            for unit in receipt["services"]:
                try:
                    remaining(True)
                    clean = isolation.stop_service(unit, deadline=deadline)
                    receipt["cleanup"][unit] = clean
                    if not clean:
                        cleanup_errors.append(f"Unconfirmed service cleanup: {unit}")
                except BaseException as exc:
                    cleanup_errors.append(f"{unit}: {exc}")
            try:
                self.assertEqual(workspace.fingerprints(project), inputs)
                if latest and not cleanup_errors:
                    receipt["final_cleanup_observations"] = stopped(latest, cleanup=True)
                remaining(True)
            except BaseException as exc:
                cleanup_errors.append(f"final integrity/cleanup: {exc}")
            receipt["cleanup_errors"] = cleanup_errors
            receipt["elapsed_seconds"] = time.monotonic() - began
            # Failed scientific acceptance still exposes the available arguments.
            excerpts = receipt.setdefault("scientific_excerpts", {})
            for name in ("acknowledged", "independent_check", "response"):
                observation = receipt["milestones"].get(name, {})
                text = observation.get("text") or observation.get("handoff")
                if text:
                    excerpts.setdefault(name, text[:3500])
            if (project / "outputs/REPORT.md").is_file():
                try:
                    excerpts.setdefault("synthesis", read("outputs/REPORT.md")[:7000])
                except (OSError, ValueError, AssertionError) as exc:
                    cleanup_errors.append(f"read final synthesis: {exc}")
            if receipt.get("checks_passed") and not cleanup_errors and failure is None:
                receipt["outcome"] = "passed"
            (run / "receipt.json").write_text(json.dumps(receipt, indent=2, default=str) + "\n")
            print(f"M3 outcome: {receipt['outcome']}; receipt: {run / 'receipt.json'}", flush=True)
            for label, excerpt in receipt.get("scientific_excerpts", {}).items():
                print(f"\nM3 {label}:\n{excerpt}", flush=True)
            for key in ("failure", "numerics", "accounting", "cleanup", "cleanup_errors"):
                print(f"M3 {key}: {json.dumps(receipt.get(key))}", flush=True)
            if cleanup_errors and failure is None:
                self.fail("; ".join(cleanup_errors))
