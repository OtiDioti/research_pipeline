"""Opt-in paid M1 acceptance, run by the pipeline in its authorized host context.

No doubles or supplied solution: Codex authors every scientific output. The fixed
script/data interface belongs to this demonstration, not to the product.
"""
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
from urllib.parse import unquote, urlsplit

from tests import use_checkout

use_checkout()
from research_pipeline import codex, isolation, workspace


QUESTIONS = """# Periodic quadrature investigation

Determine how periodic trapezoidal quadrature converges for
I(a) = integral from 0 to 2*pi of 1/(a-cos(theta)) dtheta, a > 1,
as complex singularities approach the real axis.
Read the starting note and form a concrete revisable plan before computation.
Find and assess relevant primary literature; give citations, URLs, dates,
relevance, and honest full-text versus abstract-only/inaccessible access quality.
Save at least one retrieved primary source under sources/ and link it from
LITERATURE.md. Do not invent access or claim field novelty.
Derive a reference integral and an error/convergence argument in work/DERIVATION.md.
Distinguish truncation error from floating-point effects and state assumptions.

Write and execute your own standard-library Python work/compute.py with interface:
    python3 /project/work/compute.py --output /project/work/results.json
It must actually compute quadrature estimates for every combination of
a = 1.01, 1.1, 2.0 and n = 16, 32, 64, 128, 256, 512.
Save JSON {"rows": [{"a": ..., "n": ..., "estimate": ...}, ...]}.
Additional fields are welcome. Use an output path argument so the saved
calculation can be reproduced without overwriting original data.
Preserve parameters, software versions and exact rerun instructions.
Write useful linked preliminary findings in outputs/REPORT.md, linking the plan,
literature assessment, derivation, code and data; discuss limitations and next
questions. No independent scientific verification is provided by this session.
"""

NOTE = """# Starting hypothesis

Nearby complex singularities may control convergence, and nearly singular cases
may require finer grids. This is a tentative hypothesis to investigate, not a
provided result. Check the limits of the numerical evidence.
"""


@unittest.skipUnless(os.environ.get("RESEARCH_PIPELINE_M1_LIVE") == "1",
                     "Live M1 requires explicit RESEARCH_PIPELINE_M1_LIVE=1 in an authorized host; no inference started")
class LiveM1Acceptance(unittest.TestCase):
    def test_actual_research_and_bounded_reproduction(self):
        output = os.environ.get("RESEARCH_PIPELINE_M1_OUTPUT_DIR")
        self.assertTrue(output, "Enabled live acceptance requires RESEARCH_PIPELINE_M1_OUTPUT_DIR")
        base = Path(output).absolute()
        base.mkdir(parents=True, exist_ok=True)
        run = Path(tempfile.mkdtemp(prefix="m1-live-", dir=base))
        run.chmod(0o700)
        project = run / "project"
        (project / "starting_evidence").mkdir(parents=True)
        (project / "starting_evidence/RESEARCH_QUESTIONS.md").write_text(QUESTIONS)
        (project / "starting_evidence/STARTING_NOTE.md").write_text(NOTE)
        (project / "AGENTS.md").write_text(
            "Use deterministic standard-library calculations. Report unsuccessful approaches honestly.\n")
        before = workspace.fingerprints(project)
        receipt = {"project": str(project), "commands": [], "outcome": "failed",
                   "limitations": codex.LIMITATIONS, "cleanup": {}, "protected_inputs": before}
        reproduction = None
        print(f"\nM1 private acceptance artifacts: {run}", flush=True)

        def command(args, name, timeout=20):
            receipt["commands"].append(shlex.join(args))
            print(f"M1 command: {shlex.join(args)}", flush=True)
            # On an outer timeout first allow the CLI's signal handler to stop
            # its service. The finally block also stops every known service.
            with (run / f"{name}.stdout").open("wb") as out, \
                 (run / f"{name}.stderr").open("wb") as err:
                process = subprocess.Popen(args, stdout=out, stderr=err)
                try:
                    return process.wait(timeout=timeout)
                except BaseException:
                    if process.poll() is None:
                        process.send_signal(signal.SIGTERM)
                        try:
                            process.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                    raise

        def check_rows(path):
            payload = json.loads(path.read_text())
            rows = payload["rows"]
            self.assertEqual(len(rows), 18, "Expected the entire specified parameter grid")
            values = {}
            for row in rows:
                a, n, estimate = row["a"], row["n"], row["estimate"]
                self.assertIn(a, (1.01, 1.1, 2.0))
                self.assertIn(n, (16, 32, 64, 128, 256, 512))
                self.assertTrue(math.isfinite(estimate) and estimate > 0)
                self.assertNotIn((a, n), values)
                values[a, n] = estimate
            for a in (1.01, 1.1, 2.0):
                reference = 2 * math.pi / math.sqrt(a * a - 1)
                self.assertTrue(math.isclose(values[a, 512], reference, rel_tol=1e-10),
                                f"Finest quadrature disagrees with reference for a={a}")
            reference = 2 * math.pi / math.sqrt(1.01**2 - 1)
            early = abs(values[1.01, 16] - reference)
            late = abs(values[1.01, 256] - reference)
            self.assertGreater(early, 1e-4, "No resolved coarse-grid truncation error")
            self.assertLess(late, early * 1e-6, "No meaningful numerical convergence")
            return values

        try:
            start = [sys.executable, "-m", "research_pipeline", "start", str(project),
                     "--wall-seconds", "600", "--memory-mib", "2048",
                     "--max-tasks", "128", "--cpu-percent", "100"]
            code = command(start, "start", timeout=630)
            inspect = [sys.executable, "-m", "research_pipeline", "inspect", str(project)]
            self.assertEqual(command(inspect + ["--json"], "inspect-json"), 0)
            self.assertEqual(command(inspect, "inspect"), 0)
            state = json.loads((run / "inspect-json.stdout").read_text())
            receipt["state"] = state
            self.assertEqual(code, 0, f"Real CLI start failed ({code}): {state.get('reason')}; see {run}")
            self.assertEqual(state["state"], "completed")
            self.assertTrue(state["cleanup_ok"])
            self.assertTrue(state["inputs_unchanged"])
            self.assertGreater(state["telemetry"]["successful_commands"], 0)
            self.assertFalse(workspace.validate_deliverables(project))

            for rel in (*workspace.REQUIRED, "work/DERIVATION.md"):
                text = (project / rel).read_text()
                self.assertTrue(text.strip(), f"Empty scientific artifact {rel}")
                # Scientific artifacts, not operational/model transcripts.
                print(f"\nM1 scientific artifact {rel}:\n{text[:16000]}", flush=True)
            literature = (project / "sources/LITERATURE.md").read_text()
            self.assertRegex(literature, r"https?://")
            self.assertRegex(literature.lower(), r"full[\s-]*text|abstract")
            source_files = [p for p in (project / "sources").rglob("*")
                            if p.is_file() and not p.is_symlink()
                            and p.name not in ("LITERATURE.md", "FOLDER_CONTENT.md")]
            self.assertTrue(any(p.stat().st_size >= 500 for p in source_files),
                            "No substantial retrieved primary-source artifact saved")
            local_links = []
            for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", literature):
                url = urlsplit(target)
                if not url.scheme and not url.netloc and url.path:
                    local_links.append((project / "sources" / unquote(url.path)).resolve())
            self.assertTrue(any(p.resolve() in local_links for p in source_files),
                            "Literature assessment does not link saved source material")
            original = check_rows(project / "work/results.json")
            receipt["numerical_checks"] = "18 finite grid estimates; reference and resolved convergence passed"
            artifacts = ["work/compute.py", "work/results.json", "work/DERIVATION.md",
                         *workspace.REQUIRED]
            receipt["artifact_sha256"] = {
                rel: hashlib.sha256((project / rel).read_bytes()).hexdigest() for rel in artifacts}

            reproduction = isolation.Config(wall_seconds=60, memory_mib=512, max_tasks=32,
                                            cpu_percent=100, deadline=time.monotonic() + 60)
            argv = ["/usr/bin/python3", "/project/work/compute.py",
                    "--output", "/project/work/reproduced.json"]
            receipt["reproduction_invocation"] = {
                "api": "research_pipeline.isolation.run_isolated",
                "project": str(project), "config": asdict(reproduction), "argv": argv}
            # An executable rerun command with a fresh monotonic deadline.
            rerun = (
                "from pathlib import Path; import time; from research_pipeline import isolation; "
                "c = isolation.Config(wall_seconds=60, memory_mib=512, max_tasks=32, "
                "cpu_percent=100, deadline=time.monotonic()+60); "
                f"r = isolation.run_isolated(c, Path({str(project)!r}), {argv!r}); "
                "print(r); raise SystemExit(r.returncode if r.cleanup_ok else 4)")
            receipt["reproduction_rerun_command"] = shlex.join([sys.executable, "-c", rerun])
            print(f"M1 production launcher invocation: {receipt['reproduction_invocation']}", flush=True)
            print(f"M1 reproduction rerun: {receipt['reproduction_rerun_command']}", flush=True)
            with (run / "reproduce.stdout").open("wb") as out, \
                 (run / "reproduce.stderr").open("wb") as err:
                def capture(channel, data):
                    stream = out if channel == "stdout" else err
                    # Continue draining after the private diagnostic cap.
                    stream.write(data[:max(0, 4 * 1024 * 1024 - stream.tell())])
                result = isolation.run_isolated(reproduction, project, argv, on_event=capture)
            receipt["reproduction"] = asdict(result)
            self.assertEqual(result.returncode, 0, f"Isolated reproduction failed: {run}")
            self.assertTrue(result.cleanup_ok)
            reproduced = check_rows(project / "work/reproduced.json")
            for key, value in original.items():
                self.assertTrue(math.isclose(value, reproduced[key], rel_tol=1e-12, abs_tol=1e-12),
                                f"Reproduction differs for {key}")
            self.assertEqual(hashlib.sha256((project / "work/results.json").read_bytes()).hexdigest(),
                             receipt["artifact_sha256"]["work/results.json"])
            receipt["reproduction_outcome"] = "All 18 estimates agree within rtol=atol=1e-12"
            receipt["outcome"] = "passed"
        except BaseException as exc:
            receipt["failure"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            try:
                state_path = project / ".research_pipeline/run.json"
                state = json.loads(state_path.read_text()) if state_path.exists() else {}
                receipt["state"] = state
                units = [state["service"]] if state.get("service_attempted") else []
                if reproduction:
                    units.append(reproduction.unit)
                for unit in units:
                    stopped = isolation.stop_service(unit)
                    receipt["cleanup"][unit] = {"confirmed": stopped}
                self.assertTrue(all(v["confirmed"] for v in receipt["cleanup"].values()),
                                f"Cannot confirm service/descendant cleanup: {receipt['cleanup']}")
                receipt["inputs_unchanged"] = workspace.fingerprints(project) == before
                self.assertTrue(receipt["inputs_unchanged"])
                self.assertFalse((project / "starting_evidence/FOLDER_CONTENT.md").exists())
                # Reconcile navigation after reproduction, once jobs have stopped.
                if state.get("cleanup_ok") and all(v["confirmed"] for v in receipt["cleanup"].values()):
                    workspace.refresh_indexes(project)
            except BaseException as exc:
                receipt["outcome"] = "failed"
                receipt["cleanup_or_integrity_failure"] = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                (run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
                print("M1 acceptance receipt:\n" + json.dumps(receipt, indent=2), flush=True)
