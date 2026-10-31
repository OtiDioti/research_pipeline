"""Candidate-local subprocess coverage of immutable readable view CLI controls and recovery."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory
from functools import partial
from unittest.mock import patch

from research_pipeline import cli_views
from research_pipeline.snapshot import RootSelector, SnapshotSelection
from research_pipeline.view_plan import plan_readable_snapshot
from tests.view_refresh_fixtures import RefreshFixture, refresh_limits
from tests.snapshot_fixtures import limits
from tests.test_store import record, request

SRC = Path(__file__).resolve().parents[1] / "src"


class CliViewTests(RefreshFixture, unittest.TestCase):
    """Exercise real stores, guarded controls, module entry points and retained publications."""

    def setUp(self):
        """Seed the accepted refresh fixture and independently retain its unedited manifest."""
        # CLI source protection excludes the complete candidate, including TMPDIR.
        with patch("tests.view_capture_fixtures.TemporaryDirectory", partial(TemporaryDirectory, dir="/tmp")):
            super().setUp()
        self.controls = self.parent / "controls"
        self.controls.mkdir(mode=0o700)
        self.config = self.control("config", dict(format="research_pipeline.cli_config", version=1,
                                   store=str(self.runtime), protected_roots=[]))
        self.selected = self.control("selection", dict(format="research_pipeline.cli_snapshot_selection", version=1,
            project=dict(record_id="project", revision=1), roots=[]))
        self.baseline = self.controls / "baseline"
        self.baseline.write_bytes(self.plan.manifest_bytes)
        self.baseline.chmod(0o400)
        self.destination = self.parent / "output"

    def control(self, name, value):
        """Write a complete synthetic private authored JSON control and return its path."""
        path = self.controls / name
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)
        return path

    def limit_value(self, command):
        """Return complete independent budgets for the selected CLI operation."""
        value = dict(format="research_pipeline.cli_readable_limits", version=1, command=command)
        if command in cli_views.WRITERS:
            value["snapshot_limits"] = limits().to_dict()
        if command in ("generate-readable-view", "inspect-readable-view"):
            value["view_limits"] = dict(plan_limits=limits().to_dict(), max_entries=4096,
                                        max_depth=40, max_open_descriptors=4096)
        else:
            value["refresh_limits"] = asdict(refresh_limits())
        return value

    def arguments(self, command="generate-readable-view", **options):
        """Build explicit arguments and command-bound limits, retaining override paths and identities."""
        defaults = dict(config=self.config, limits=self.control(command + "-limits", self.limit_value(command)))
        if command in cli_views.WRITERS:
            defaults.update(selection=self.selected, destination=self.destination)
        if command == "refresh-readable-view":
            defaults.update(prior_view=self.view, baseline_manifest=self.baseline,
                expected_base_plan_id=self.plan.plan_id,
                expected_base_manifest_sha256=hashlib.sha256(self.plan.manifest_bytes).hexdigest())
        if command == "inspect-readable-view":
            defaults["view"] = self.view
        defaults.update(options)
        return [command, *(item for name, value in defaults.items()
                           for item in ("--" + name.replace("_", "-"), str(value)))]

    def invoke(self, arguments=None, *, prelude=None, expected=0):
        """Run the actual candidate CLI in a fresh private cwd, with optional private fault setup."""
        arguments = self.arguments() if arguments is None else arguments
        program = (["-m", "research_pipeline"] if prelude is None else
                   ["-c", prelude + '\nimport runpy\nrunpy.run_module("research_pipeline", run_name="__main__")\n'])
        result = subprocess.run([sys.executable, "-B", *program, *arguments], cwd=self.parent,
            env={**os.environ, "PYTHONPATH": str(SRC), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stderr.decode(errors="replace"))
        if expected == 0:
            self.assertEqual(result.stderr, b"")
        return result

    def result(self, process):
        """Require a compact ASCII versioned success envelope and return the operation observation."""
        value = json.loads(process.stdout)
        self.assertEqual(set(value), {"format", "version", "command", "status", "result"})
        self.assertEqual(value["format"], "research_pipeline.cli_result")
        self.assertEqual(value["version"], 1)
        self.assertEqual(value["status"], "ok")
        self.assertEqual(process.stdout, (json.dumps(value, sort_keys=True, separators=(",", ":"),
                                                    ensure_ascii=True) + "\n").encode("ascii"))
        return value["result"]

    def diagnostic(self, process, code):
        """Require bounded exact diagnostic fields without a false success document."""
        self.assertEqual(process.stdout, b"")
        self.assertLessEqual(len(process.stderr), 65536)
        self.assertTrue(process.stderr.isascii())
        value = json.loads(process.stderr)
        self.assertEqual(set(value), {"format", "version", "command", "code", "message", "context"})
        self.assertEqual(value["code"], code)
        self.assertEqual(set(value["context"]), set(cli_views.CONTEXT_FIELDS))
        return value["context"]

    def test_initial_exact_current_and_once_without_admission(self):
        """Capture exactly once without artifact access during planning or metadata submission."""
        self.store.submit(request("later", [record("project", revision=2, kind="project")], {"project": 1}))
        guard = '''
from research_pipeline import cli_views
from research_pipeline.store import RecordStore
original = RecordStore.capture_snapshot
count = 0
def capture(self, *args, **kwargs):
    """Require the sole metadata capture and temporarily reject artifact opens."""
    global count, active
    count += 1
    assert count == 1
    active = True
    try: return original(self, *args, **kwargs)
    finally: active = False
def forbidden(*args, **kwargs):
    """Reject metadata submission and typed admission during CLI projection."""
    raise AssertionError("unexpected submission")
RecordStore.capture_snapshot = capture
RecordStore.submit = forbidden
RecordStore.submit_typed = forbidden
import sys
active = False
def audit(event, args):
    """Forbid artifact leaf opens while capture/planning is active."""
    if active and event == "open" and isinstance(args[0], str) and len(args[0].split("/")[-1]) == 64:
        raise AssertionError("artifact read during metadata planning")
sys.addaudithook(audit)
real_plan = cli_views.plan_readable_snapshot
def plan(*args, **kwargs):
    """Audit detached planning and restore the gate before materialization."""
    global active
    active = True
    try: return real_plan(*args, **kwargs)
    finally: active = False
cli_views.plan_readable_snapshot = plan
'''
        exact = self.result(self.invoke(prelude=guard))
        self.assertEqual(set(exact), {"snapshot_id", "plan_id", "manifest_sha256", "destination", "attempt_path",
                                      "verification", "selection", "resolutions"})
        self.assertEqual(exact["resolutions"][0]["revision"], 1)
        self.assertEqual(exact["selection"]["project"]["revision"], 1)
        self.assertEqual((self.destination / "manifest.json").stat().st_mode & 0o777, 0o400)
        self.assertEqual(self.store.head("project"), 2)
        current = json.loads(self.selected.read_text())
        current["project"]["revision"] = None
        self.control("selection", current)
        actual = self.result(self.invoke(self.arguments(destination=self.parent / "current"), prelude=guard))
        self.assertEqual(actual["resolutions"][0]["revision"], 2)
        self.assertIsNone(actual["selection"]["project"]["revision"])

    def test_refresh_independent_baseline_and_offline_generation_child(self):
        """Opaque edited prior controls remain preservation; the detached baseline supplies the expected plan."""
        before_objects = {p.name: p.read_bytes() for p in (self.runtime / "objects").iterdir()}
        self.write("manifest.json", b"opaque human control edit\n")
        self.write("README.md", b"human generated-status edit\n")
        self.write("native.bin", b"\x00\xffinert")
        result = self.result(self.invoke(self.arguments("refresh-readable-view")))
        self.assertEqual(set(result), {"refresh_id", "prior_view", "prior_snapshot_id", "prior_plan_id", "capture_id",
            "preservation_plan_id", "successor_snapshot_id", "successor_plan_id", "destination", "successor_path",
            "preservation_path", "attempt_path", "same_plan", "verification", "selection", "resolutions",
            "baseline_manifest_sha256"})
        self.assertEqual((self.view / "manifest.json").read_bytes(), b"opaque human control edit\n")
        self.assertEqual((Path(result["preservation_path"]) / "controls/expected-manifest.json").read_bytes(), self.plan.manifest_bytes)
        self.assertEqual((Path(result["preservation_path"]) / "controls/observed-manifest.bin").read_bytes(), b"opaque human control edit\n")
        self.assertEqual(before_objects, {p.name: p.read_bytes() for p in (self.runtime / "objects").iterdir()})
        self.store.close()
        self.runtime.rename(self.parent / "unavailable")
        offline = self.result(self.invoke(self.arguments("inspect-readable-refresh", attempt=result["attempt_path"],
                                                        destination=self.destination, expected_refresh_id=result["refresh_id"])))
        self.assertEqual(offline["status"], "published")
        self.assertEqual(offline["historical_acknowledgment"], "not_established")
        self.assertEqual(set(offline), {"attempt_path", "destination", "status", "refresh_id", "verified_package_path",
            "successor_path", "preservation_path", "readiness_observation", "publication_observation",
            "historical_acknowledgment", "differences"})
        observed = self.result(self.invoke(self.arguments("inspect-readable-view", view=result["successor_path"])))
        self.assertEqual(observed["status"], "verified")
        self.assertEqual(set(observed), {"view", "snapshot_id", "plan_id", "manifest_sha256", "status", "differences",
                                        "historical_acknowledgment"})
        self.assertFalse(self.runtime.exists())

    def test_same_plan_then_newer_and_second_refresh(self):
        """Same-plan requests still allocate packages, and published generation children support subsequent refresh."""
        self.control("selection", dict(format="research_pipeline.cli_snapshot_selection", version=1,
                                       project=dict(record_id="project", revision=None), roots=[]))
        first = self.result(self.invoke(self.arguments("refresh-readable-view")))
        self.assertTrue(first["same_plan"])
        self.store.submit(request("later", [record("project", revision=2, kind="project")], {"project": 1}))
        second = self.result(self.invoke(self.arguments("refresh-readable-view", prior_view=first["successor_path"],
                                                        destination=self.parent / "second")))
        self.assertFalse(second["same_plan"])
        self.assertEqual(second["resolutions"][0]["revision"], 2)
        self.assertTrue(Path(first["successor_path"]).is_dir())

    def test_strict_selection_limits_and_scalar_options(self):
        """Missing revision, wrong scalar types, incomplete nested limits and wrong command binding fail early."""
        good = json.loads(self.selected.read_text())
        invalid = [dict(project=dict(record_id="project")), dict(roots=None), dict(version=True), dict(extra=1),
                   dict(project=dict(record_id="project", revision=True)),
                   dict(project=dict(record_id="project", revision=1.0))]
        for changes in invalid:
            with self.subTest(changes=changes):
                self.control("selection", {**good, **changes})
                self.diagnostic(self.invoke(expected=5), "invalid_input")
                self.assertFalse(self.destination.exists())
        self.control("selection", good)
        for group, field, number, code in (("snapshot_limits", "max_roots", 1025, "limit_exceeded"),
                ("view_limits", "max_open_descriptors", 4097, "limit_exceeded"),
                ("view_limits", "max_depth", True, "invalid_input")):
            value = self.limit_value("generate-readable-view")
            value[group][field] = number
            path = self.control("bad-limits", value)
            self.diagnostic(self.invoke(self.arguments(limits=path), expected=5), code)
        self.diagnostic(self.invoke(self.arguments("refresh-readable-view", expected_base_plan_id="A" * 64), expected=5), "invalid_input")
        self.invoke(self.arguments() + ["--max-selection-bytes", "-1"], expected=2)
        self.invoke(self.arguments() + ["--config", str(self.config)], expected=2)

    def test_baseline_pins_noncanonical_limits_and_layout(self):
        """Require an independent regular baseline with exact canonical bytes and both retained identity pins."""
        for option in ("expected_base_plan_id", "expected_base_manifest_sha256"):
            self.diagnostic(self.invoke(self.arguments("refresh-readable-view", **{option: "0" * 64}), expected=6), "integrity_error")
        self.diagnostic(self.invoke(self.arguments("refresh-readable-view", baseline_manifest=self.view / "manifest.json"), expected=5), "unsafe_layout")
        linked = self.controls / "linked"
        os.link(self.baseline, linked)
        self.diagnostic(self.invoke(self.arguments("refresh-readable-view"), expected=5), "unsafe_layout")
        linked.unlink()
        self.baseline.chmod(0o600)
        self.baseline.write_bytes(self.plan.manifest_bytes + b"\n")
        self.diagnostic(self.invoke(self.arguments("refresh-readable-view"), expected=5), "invalid_input")
        self.baseline.write_bytes(self.plan.manifest_bytes)
        value = self.limit_value("refresh-readable-view")
        value["refresh_limits"]["capture_limits"]["plan_limits"]["max_roots"] -= 1
        path = self.control("small", value)
        self.diagnostic(self.invoke(self.arguments("refresh-readable-view", limits=path), expected=5), "limit_exceeded")
        self.assertFalse(self.destination.exists())

    def test_prepublication_output_and_admission_limits(self):
        """Too-small output and descriptor/depth budgets fail without allocating attempt siblings."""
        before = set(self.parent.iterdir())
        for command in cli_views.WRITERS:
            self.diagnostic(self.invoke(self.arguments(command, max_output_bytes=1), expected=5), "limit_exceeded")
            self.assertEqual(set(self.parent.iterdir()), before)
        value = self.limit_value("generate-readable-view")
        for field in ("max_depth", "max_open_descriptors", "max_entries"):
            changed = json.loads(json.dumps(value))
            changed["view_limits"][field] = 1
            path = self.control("small", changed)
            self.diagnostic(self.invoke(self.arguments(limits=path), expected=5), "limit_exceeded")
            self.assertEqual(set(self.parent.iterdir()), before)

    def test_missing_collision_and_offline_observations(self):
        """Separate absent explicit inputs, occupied leaves, internal controls and offline incomplete evidence."""
        self.diagnostic(self.invoke(self.arguments(selection=self.controls / "missing"), expected=3), "missing")
        self.diagnostic(self.invoke(self.arguments("inspect-readable-view", view=self.parent / "missing"), expected=3), "missing")
        self.destination.symlink_to(self.parent / "absent")
        self.diagnostic(self.invoke(expected=4), "conflict")
        self.destination.unlink()
        observed = self.result(self.invoke(self.arguments("inspect-readable-refresh", destination=self.destination,
            attempt=self.parent / (".readable-refresh-attempt-" + "a" * 32))))
        self.assertEqual(observed["status"], "incomplete_preparation")
        self.assertIsNone(observed["successor_path"])
        self.write("README.md", b"edited")
        observed = self.result(self.invoke(self.arguments("inspect-readable-view")))
        self.assertEqual(observed["status"], "diverged")
        self.assertTrue(observed["differences"])
        self.assertEqual(set(observed["differences"][0]), {"relative_path", "code", "detail"})
        self.diagnostic(self.invoke(self.arguments("inspect-readable-view", expected_plan_id="0" * 64), expected=6), "integrity_error")

    def test_interruption_metadata_before_and_after_rename(self):
        """Real KeyboardInterrupt at lifecycle seams retains exact paths and honest publication uncertainty."""
        for index, boundary in enumerate(("after_attempt_reservation", "after_intent", "after_complete_package", "after_ready", "after_rename")):
            prelude = '''
from research_pipeline import view_refresh
def fault(boundary):
    """Interrupt one actual lifecycle boundary without changing production publication globals."""
    if boundary == %r: raise KeyboardInterrupt()
view_refresh._fault = fault
''' % boundary
            destination = self.parent / ("interrupted-" + str(index))
            process = self.invoke(self.arguments("refresh-readable-view", destination=destination), prelude=prelude,
                                  expected=7 if boundary == "after_rename" else 6)
            context = self.diagnostic(process, "effects_uncertain" if boundary == "after_rename" else "operational_error")
            self.assertEqual(context["destination"], str(destination))
            self.assertIsNotNone(context["attempt_path"])
            observed = self.result(self.invoke(self.arguments("inspect-readable-refresh", destination=destination,
                attempt=context["attempt_path"])))
            self.assertEqual(observed["status"], "published" if boundary == "after_rename" else
                             "complete_unpublished" if boundary in ("after_complete_package", "after_ready") else "incomplete_preparation")

    def test_stdout_failure_preserves_recovery_and_offline_repeat(self):
        """Writer output failure reports effects uncertainty; read-only output failure allows repeating inspection."""
        prelude = '''
import sys
class Broken:
    """Fail flush after accepting a short chunk without ever acknowledging complete output."""
    buffer = None
    def __init__(self):
        """Expose this synthetic stream as its own binary target."""
        self.buffer = self
    def write(self, data):
        """Accept a short chunk to exercise draining."""
        return min(len(data), 7)
    def flush(self):
        """Inject a real output-resource failure."""
        raise OSError("flush failed")
    def close(self):
        """Close without sending shutdown retries."""
        pass
sys.stdout = Broken()
'''
        context = self.diagnostic(self.invoke(prelude=prelude, expected=7), "effects_uncertain")
        self.assertTrue(self.destination.is_dir())
        self.assertTrue(Path(context["attempt_path"]).is_dir())
        self.diagnostic(self.invoke(self.arguments("inspect-readable-view"), prelude=prelude, expected=6), "output_failed")
        self.assertEqual(self.result(self.invoke(self.arguments("inspect-readable-view")))["status"], "verified")

    def test_deep_historical_manifest_and_independent_allowances(self):
        """Depth-64 provenance survives 69-level historical reconstruction in refresh and offline inspection."""
        from research_pipeline.domain import CreationProvenance
        value = 0
        for _ in range(62):
            value = [value]
        provenance = CreationProvenance("author", "2026-10-30T10:00:00Z", {"nested": value})
        self.store.submit(request("deep", [record("project", revision=2, kind="project", provenance=provenance,
            artifact_references=[self.artifact])], {"project": 1}))
        self.control("selection", dict(format="research_pipeline.cli_snapshot_selection", version=1,
                                      project=dict(record_id="project", revision=2), roots=[]))
        generated = self.result(self.invoke())
        baseline = self.controls / "deep-baseline"
        baseline.write_bytes((self.destination / "manifest.json").read_bytes())
        baseline.chmod(0o400)
        observed = self.result(self.invoke(self.arguments("inspect-readable-view", view=self.destination)))
        self.assertEqual(observed["plan_id"], generated["plan_id"])
        refreshed = self.result(self.invoke(self.arguments("refresh-readable-view", prior_view=self.destination,
            baseline_manifest=baseline, expected_base_plan_id=generated["plan_id"],
            expected_base_manifest_sha256=generated["manifest_sha256"], destination=self.parent / "deep-next")))
        self.assertTrue(refreshed["same_plan"])
        self.assertEqual(refreshed["baseline_manifest_sha256"], generated["manifest_sha256"])

    def test_ordered_roots_and_historical_edges_after_head_advancement(self):
        """Current roots resolve in caller order while committed outgoing references keep exact older revisions."""
        from research_pipeline.domain import RecordReference
        self.store.submit(request("edge", [record("first"), record("second")]))
        self.store.submit(request("edge-project", [record("project", revision=2, kind="project",
            record_references=[RecordReference("first", 1, "historical")])], {"project": 1}))
        self.store.submit(request("edge-advance", [record("first", revision=2)], {"first": 1}))
        self.control("selection", dict(format="research_pipeline.cli_snapshot_selection", version=1,
            project=dict(record_id="project", revision=None),
            roots=[dict(record_id="second", revision=1), dict(record_id="first", revision=None)]))
        observed = self.result(self.invoke())
        self.assertEqual(observed["resolutions"], [dict(record_id="project", revision=2),
                         dict(record_id="second", revision=1), dict(record_id="first", revision=2)])
        manifest = json.loads((self.destination / "manifest.json").read_bytes())
        records = {(item["record_id"], item["revision"]) for item in manifest["records"]}
        self.assertIn(("first", 1), records)
        self.assertIn(("first", 2), records)

    def test_absent_canonical_artifact_and_selected_record(self):
        """Missing selected roots are missing inputs; missing canonical payloads are integrity failures."""
        self.control("selection", dict(format="research_pipeline.cli_snapshot_selection", version=1,
                                      project=dict(record_id="absent", revision=1), roots=[]))
        self.diagnostic(self.invoke(expected=3), "missing")
        self.control("selection", dict(format="research_pipeline.cli_snapshot_selection", version=1,
                                      project=dict(record_id="project", revision=1), roots=[]))
        (self.runtime / "objects" / self.artifact.digest).unlink()
        context = self.diagnostic(self.invoke(expected=6), "integrity_error")
        self.assertIsNotNone(context["attempt_path"])
        self.assertFalse(self.destination.exists())

    def test_manifest_preflight_replacement_is_integrity_failure(self):
        """Identical bytes at a replacement manifest inode cannot conceal the change between inspection passes."""
        prelude = '''
from pathlib import Path
from research_pipeline import vault
real = vault._inspect_readable_view
def replace_manifest(root, **kwargs):
    """Replace only the disposable manifest after CLI admission and before the actual inspector."""
    root = Path(root)
    root.chmod(0o700)
    original = root / "manifest.json"
    replacement = root / "replacement"
    replacement.write_bytes(original.read_bytes())
    replacement.chmod(0o400)
    replacement.replace(original)
    root.chmod(0o500)
    return real(root, **kwargs)
vault._inspect_readable_view = replace_manifest
'''
        self.diagnostic(self.invoke(self.arguments("inspect-readable-view"), prelude=prelude, expected=6), "integrity_error")

    def test_unsafe_controls_and_recognizable_ancestors(self):
        """No-follow reads reject links/FIFOs and recognizable control ancestors before payload traversal."""
        for kind in ("symlink", "fifo", "mode", "hardlink"):
            path = self.controls / ("unsafe-" + kind)
            if kind == "symlink":
                path.symlink_to(self.baseline)
            elif kind == "fifo":
                os.mkfifo(path, 0o600)
            elif kind == "hardlink":
                os.link(self.baseline, path)
            else:
                path.write_bytes(self.plan.manifest_bytes)
                path.chmod(0o644)
            self.diagnostic(self.invoke(self.arguments("refresh-readable-view", baseline_manifest=path), expected=5), "unsafe_layout")
            path.unlink()
        for marker in ("refresh.json", ".work-product-proposal", "snapshot.sqlite3", "manifest.json"):
            directory = self.parent / ("ancestor-" + marker.replace(".", ""))
            directory.mkdir(mode=0o700)
            (directory / marker).write_bytes(b"inert")
            baseline = directory / "baseline"
            baseline.write_bytes(self.plan.manifest_bytes)
            baseline.chmod(0o600)
            self.diagnostic(self.invoke(self.arguments("refresh-readable-view", baseline_manifest=baseline), expected=5), "unsafe_layout")

    def publisher(self, command, destination, boundary):
        """Park an actual CLI child at a private seam using separate notification/release pipes."""
        import selectors
        read_notice, write_notice = os.pipe()
        read_release, write_release = os.pipe()
        prelude = '''
import os
from research_pipeline import vault, view_refresh
def seam(point):
    """Signal a real boundary on a private pipe and await release or an OS signal."""
    if point == %r:
        os.write(%d, b"ready")
        os.read(%d, 1)
vault._fault = seam
view_refresh._fault = seam
import runpy
runpy.run_module("research_pipeline", run_name="__main__")
''' % (boundary, write_notice, read_release)
        try:
            child = subprocess.Popen([sys.executable, "-B", "-c", prelude,
                *self.arguments(command, destination=destination)], cwd=self.parent,
                env={**os.environ, "PYTHONPATH": str(SRC), "PYTHONDONTWRITEBYTECODE": "1"},
                pass_fds=(write_notice, read_release), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            os.close(write_notice)
            os.close(read_release)
        self.addCleanup(self.stop_publisher, child, write_release)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(read_notice, selectors.EVENT_READ)
                self.assertTrue(selector.select(30), "child did not reach the boundary")
            self.assertEqual(os.read(read_notice, 5), b"ready")
        finally:
            os.close(read_notice)
        return child, write_release

    def stop_publisher(self, child, release):
        """Reap only this test child and close its owned pipe even when an assertion fails."""
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)
        os.close(release)

    def test_actual_sigint_and_offline_retained_refresh_states(self):
        """SIGINT at real lifecycle boundaries produces exact associations inspectable after runtime removal."""
        import signal
        results = []
        for index, boundary in enumerate(("after_attempt_reservation", "after_package_reservation", "after_intent",
                                           "after_complete_package", "after_ready", "after_rename")):
            destination = self.parent / ("signal-" + str(index))
            child, release = self.publisher("refresh-readable-view", destination, boundary)
            child.send_signal(signal.SIGINT)
            output, error = child.communicate(timeout=30)
            process = subprocess.CompletedProcess([], child.returncode, output, error)
            context = self.diagnostic(process, "effects_uncertain" if boundary == "after_rename" else "operational_error")
            self.assertEqual(child.returncode, 7 if boundary == "after_rename" else 6)
            results.append((boundary, destination, context))
        self.store.close()
        self.runtime.rename(self.parent / "offline-runtime")
        from tests.view_capture_fixtures import tree_state
        before = tree_state(self.parent)
        for boundary, destination, context in results:
            observed = self.result(self.invoke(self.arguments("inspect-readable-refresh", destination=destination,
                attempt=context["attempt_path"])))
            self.assertEqual(observed["status"], "published" if boundary == "after_rename" else
                "complete_unpublished" if boundary in ("after_complete_package", "after_ready") else "incomplete_preparation")
        # Arguments rewrites only our controls; observations leave all retained trees unchanged.
        after = tree_state(self.parent)
        self.assertEqual({k: v for k, v in before.items() if not k.startswith("controls")},
                         {k: v for k, v in after.items() if not k.startswith("controls")})
        self.assertFalse(self.runtime.exists())

    def test_two_cli_writers_kernel_no_replace_race(self):
        """Two actual writers both enter rename; exactly one wins and the losing evidence is retained."""
        for command in ("generate-readable-view", "refresh-readable-view"):
            destination = self.parent / command
            children = [self.publisher(command, destination, "at_rename") for _ in range(2)]
            for child, release in children:
                os.write(release, b"1")
            observations = []
            for child, release in children:
                output, error = child.communicate(timeout=30)
                observations.append(subprocess.CompletedProcess([], child.returncode, output, error))
            self.assertEqual(sorted(row.returncode for row in observations), [0, 4])
            lost = self.diagnostic(next(row for row in observations if row.returncode == 4), "conflict")
            won = self.result(next(row for row in observations if row.returncode == 0))
            self.assertNotEqual(lost["attempt_path"], won["attempt_path"])
            self.assertTrue(Path(lost["attempt_path"]).is_dir())
            if command == "refresh-readable-view":
                self.store.close()
                self.runtime.rename(self.parent / "race-runtime-unavailable")
                observed = self.result(self.invoke(self.arguments("inspect-readable-refresh", destination=destination,
                    attempt=lost["attempt_path"])))
                self.assertEqual(observed["status"], "competing_destination")
            else:
                preparation = Path(lost["attempt_path"].replace(".readable-view-", ".readable-generation-"))
                self.assertEqual(self.result(self.invoke(self.arguments("inspect-readable-view", view=preparation)))["status"], "verified")

    def test_os_sync_close_and_output_failures(self):
        """Real OS failures before publication remain operational; post-rename sync/close failures disavow success."""
        for index, (boundary, operation) in enumerate((("after_intent", "fsync"), ("after_rename", "fsync"),
                                                      ("after_published", "close"))):
            prelude = '''
import os, errno
from research_pipeline import vault
real = os.%s
armed = False
def seam(point):
    """Arm failure only after the requested real lifecycle boundary."""
    global armed
    if point == %r: armed = True
def fail(fd):
    """Report an actual OS error, closing real descriptors before simulated close acknowledgment loss."""
    global armed
    if armed:
        armed = False
        if %r == "close": real(fd)
        raise OSError(errno.EIO, "injected resource failure")
    return real(fd)
vault._fault = seam
os.%s = fail
''' % (operation, boundary, operation, operation)
            expected = 6 if boundary == "after_intent" else 7
            self.diagnostic(self.invoke(self.arguments(destination=self.parent / ("os-failure-" + str(index))),
                prelude=prelude, expected=expected), "operational_error" if expected == 6 else "effects_uncertain")

    def test_real_hot_journal_recovery_does_not_admit_interrupted_record(self):
        """Writer opening recovers a hot rollback journal before its sole detached capture."""
        from tests.test_assessment_store import metadata
        before = metadata(self.runtime)
        program = '''
import os, sys
from research_pipeline import store as module
from research_pipeline.domain import RecordEnvelope, CreationProvenance, Submission
provenance = CreationProvenance("author", "2026-10-30T12:00:00Z", {})
with module.RecordStore.open(sys.argv[1]) as store:
    envelope = RecordEnvelope("interrupted", 1, "research_context", {"large": "x" * 3000000}, provenance)
    def crash(point):
        """Exit only after actual first-revision writes force journal page spill."""
        if point == "after_first_revision": os._exit(73)
    module._fault = crash
    store.submit(Submission("interrupted", provenance, [envelope], {"interrupted": 0}))
raise AssertionError("crash seam not reached")
'''
        process = subprocess.run([sys.executable, "-B", "-c", program, str(self.runtime)], cwd=self.parent,
            env={**os.environ, "PYTHONPATH": str(SRC)}, capture_output=True, timeout=40)
        self.assertEqual(process.returncode, 73, process.stderr)
        journal = self.runtime / "metadata.sqlite3-journal"
        self.assertGreater(journal.stat().st_size, 512)
        self.invoke()
        self.assertFalse(journal.exists())
        self.assertEqual(metadata(self.runtime), before)

    def test_coherent_alternative_baseline_still_requires_original_pins(self):
        """A different canonical plan cannot replace the retained historical assertion under unchanged pins."""
        alternative = plan_readable_snapshot(self.store.capture_snapshot(
            SnapshotSelection(RootSelector("project", 1), ()), limits=limits()))
        self.assertNotEqual(alternative.plan_id, self.plan.plan_id)
        self.baseline.chmod(0o600)
        self.baseline.write_bytes(alternative.manifest_bytes)
        self.diagnostic(self.invoke(self.arguments("refresh-readable-view"), expected=6), "integrity_error")
        self.assertFalse(self.destination.exists())

    def test_short_partial_flush_close_output_and_store_close(self):
        """Drain short output, reject partial/flush/close failures and retain identities after store-close failure."""
        for command in ("generate-readable-view", "inspect-readable-view"):
            for index, fault in enumerate(("short", "partial", "flush", "close")):
                prelude = '''
import sys
original = sys.stdout
class Output:
    """Delegate to real stdout with one selected acknowledgment fault and no shutdown retries."""
    @property
    def buffer(self):
        """Expose the wrapper as its own binary output target."""
        return self
    def fileno(self):
        """Return the real recipient descriptor for shutdown silencing."""
        return original.fileno()
    def write(self, data):
        """Drain real short writes, or deliver a real partial prefix before failing."""
        if %r == "partial":
            original.buffer.write(data[:7])
            original.flush()
            raise BrokenPipeError("partial output")
        return original.buffer.write(data[:3] if %r == "short" else data)
    def flush(self):
        """Fail the selected flush barrier after accepting bytes."""
        if %r == "flush": raise OSError("flush failed")
        original.flush()
    def close(self):
        """Fail the selected close acknowledgment without an interpreter shutdown retry."""
        if %r == "close": raise OSError("close failed")
        original.close()
sys.stdout = Output()
''' % (fault, fault, fault, fault)
                options = dict(destination=self.parent / ("output-" + str(index))) if command in cli_views.WRITERS else {}
                expected = 0 if fault == "short" else 7 if command in cli_views.WRITERS else 6
                process = self.invoke(self.arguments(command, **options), prelude=prelude, expected=expected)
                if fault == "short":
                    self.result(process)
                else:
                    self.assertNotIn(b"Traceback", process.stderr)
                    value = json.loads(process.stderr)
                    self.assertEqual(value["code"], "effects_uncertain" if command in cli_views.WRITERS else "output_failed")
                    if fault == "partial":
                        self.assertEqual(len(process.stdout), 7)
                    if command in cli_views.WRITERS:
                        self.assertTrue(Path(value["context"]["attempt_path"]).is_dir())
        prelude = '''
from research_pipeline.store import RecordStore
real = RecordStore.close
def close(self):
    """Close the real store, then fail its post-publication acknowledgment."""
    real(self)
    raise OSError("store close failure")
RecordStore.close = close
'''
        context = self.diagnostic(self.invoke(self.arguments(destination=self.parent / "store-close"),
                                             prelude=prelude, expected=7), "effects_uncertain")
        self.assertTrue(Path(context["attempt_path"]).is_dir())
        self.assertTrue(Path(context["destination"]).is_dir())

    def test_offline_inconsistent_evidence_is_observation_and_never_repair(self):
        """Contradictory retained markers yield exit-zero inconsistent evidence without writing any package."""
        from tests.view_capture_fixtures import tree_state
        result = self.result(self.invoke(self.arguments("refresh-readable-view")))
        marker = Path(result["attempt_path"]) / "published.json"
        marker.chmod(0o600)
        marker.write_bytes(marker.read_bytes().replace(b'"version":1', b'"version":true'))
        marker.chmod(0o400)
        self.store.close()
        self.runtime.rename(self.parent / "unavailable-runtime")
        package_before = tree_state(self.destination)
        attempt_before = tree_state(Path(result["attempt_path"]))
        observed = self.result(self.invoke(self.arguments("inspect-readable-refresh", destination=self.destination,
            attempt=result["attempt_path"])))
        self.assertEqual(observed["status"], "inconsistent")
        self.assertIsNone(observed["successor_path"])
        self.assertEqual(tree_state(self.destination), package_before)
        self.assertEqual(tree_state(Path(result["attempt_path"])), attempt_before)

    def test_view_descriptor_depth_and_manifest_exact_admission(self):
        """Canonical depth, conservative descriptors and external manifest caps admit equality and reject one-under."""
        ancestors = len(self.destination.parent.parts) + len(self.runtime.parts)
        reservation = 64 + 2 * ancestors + 2 * (len(self.plan.directories) + len(self.plan.generated_files)
            + len(self.plan.artifact_copies) + len({item.digest for item in self.plan.artifact_copies}))
        depth = max(len(item.relative_path.split("/")) if item.relative_path else 0
                    for item in (*self.plan.directories, *self.plan.generated_files, *self.plan.artifact_copies))
        value = self.limit_value("generate-readable-view")
        value["view_limits"].update(max_depth=depth, max_open_descriptors=reservation)
        selected = self.control("boundary", value)
        self.invoke(self.arguments(limits=selected))
        for name, boundary in (("max_depth", depth), ("max_open_descriptors", reservation)):
            invalid = json.loads(json.dumps(value))
            invalid["view_limits"][name] = boundary - 1
            selected = self.control("boundary", invalid)
            self.diagnostic(self.invoke(self.arguments(limits=selected, destination=self.parent / "too-small"), expected=5), "limit_exceeded")
            self.assertFalse((self.parent / "too-small").exists())
        maximum = len(self.plan.manifest_bytes)
        self.invoke(self.arguments("inspect-readable-view", max_manifest_bytes=maximum))
        self.diagnostic(self.invoke(self.arguments("inspect-readable-view", max_manifest_bytes=maximum - 1), expected=5), "limit_exceeded")
        self.invoke(self.arguments("refresh-readable-view", max_manifest_bytes=maximum, destination=self.parent / "bounded-refresh"))
        self.diagnostic(self.invoke(self.arguments("refresh-readable-view", max_manifest_bytes=maximum - 1,
                                                  destination=self.parent / "small-manifest"), expected=5), "limit_exceeded")

    def test_unavailable_offline_runtime_is_never_opened(self):
        """Offline config contributes exclusions only, even when an attempted store open would raise."""
        result = self.result(self.invoke(self.arguments("refresh-readable-view")))
        self.store.close()
        self.runtime.rename(self.parent / "offline")
        prelude = '''
from research_pipeline.store import RecordStore
def forbidden(*args, **kwargs):
    """Forbid any live-store opening by an offline inspector."""
    raise AssertionError("offline runtime access")
RecordStore.open = forbidden
'''
        self.invoke(self.arguments("inspect-readable-view"), prelude=prelude)
        self.invoke(self.arguments("inspect-readable-refresh", destination=self.destination,
                                  attempt=result["attempt_path"]), prelude=prelude)
        self.diagnostic(self.invoke(self.arguments("inspect-readable-refresh", destination=self.destination,
            attempt=result["attempt_path"], expected_refresh_id="0" * 64), prelude=prelude, expected=6), "integrity_error")
        self.assertFalse(self.runtime.exists())

    def test_observed_control_ancestor_disappearance_is_integrity(self):
        """Renaming a pinned parent or higher ancestor cannot masquerade as an initially missing input."""
        for option in ("limits", "selection", "baseline_manifest"):
            for higher in (False, True):
                with self.subTest(option=option, higher=higher):
                    command = "refresh-readable-view" if option == "baseline_manifest" else "generate-readable-view"
                    ancestor = self.parent / (option + str(higher))
                    directory = ancestor / "private"
                    directory.mkdir(parents=True, mode=0o700)
                    ancestor.chmod(0o700)
                    target = directory / "control"
                    data = (self.plan.manifest_bytes if option == "baseline_manifest" else
                            self.selected.read_bytes() if option == "selection" else
                            json.dumps(self.limit_value(command)).encode())
                    target.write_bytes(data)
                    target.chmod(0o600)
                    moved = ancestor if higher else directory
                    prelude = '''
from pathlib import Path
from research_pipeline import cli_controls
real = cli_controls.read_control
def read(parent, name, path, maximum, *, modes):
    """Arm the deterministic seam only for the selected control, leaving config reads intact."""
    previous = cli_controls._fault
    def rename(boundary):
        """Detach a held ancestor while the descriptor-relative leaf remains unchanged."""
        if boundary == "after_control_read":
            Path(%r).rename(%r)
    if str(path) == %r:
        cli_controls._fault = rename
    try:
        return real(parent, name, path, maximum, modes=modes)
    finally:
        cli_controls._fault = previous
cli_controls.read_control = read
''' % (str(moved), str(moved.with_name(moved.name + "-moved")), str(target))
                    before = set(self.parent.iterdir())
                    context = self.diagnostic(self.invoke(self.arguments(command, **{option: target}),
                        prelude=prelude, expected=6), "integrity_error")
                    self.assertIsNone(context["attempt_path"])
                    self.assertFalse(self.destination.exists())
                    self.assertFalse(any(p.name.startswith(".readable-") for p in set(self.parent.iterdir()) - before))

    def test_control_initial_absence_replacement_and_checked_close(self):
        """Explicit absent leaves/parents stay missing; replacement and real close faults keep distinct errors."""
        for option in ("limits", "selection", "baseline_manifest"):
            command = "refresh-readable-view" if option == "baseline_manifest" else "generate-readable-view"
            for path in (self.controls / "absent", self.parent / "absent-parent" / "control"):
                with self.subTest(option=option, path=path):
                    self.diagnostic(self.invoke(self.arguments(command, **{option: path}), expected=3), "missing")
            target = (self.baseline if option == "baseline_manifest" else self.selected if option == "selection"
                      else self.control("fault-limits", self.limit_value(command)))
            for fault in ("replace", "close"):
                prelude = '''
import os
from pathlib import Path
from research_pipeline import cli_controls
real_read, real_close = cli_controls.read_control, os.close
active = False
def close(fd):
    """Close the actual descriptor before reporting the selected input acknowledgment failure."""
    real_close(fd)
    if active:
        raise OSError(5, "checked control close failed")
def read(parent, name, path, maximum, *, modes):
    """Scope replacement and checked-close injection to the intended explicit input."""
    global active
    previous = cli_controls._fault
    def mutate(boundary):
        """Replace only the held leaf, preserving its bytes and private mode."""
        if boundary == "after_control_read":
            other = Path(str(path) + ".replacement")
            other.write_bytes(Path(path).read_bytes())
            other.chmod(0o600)
            other.replace(path)
    if str(path) == %r:
        active = %r == "close"
        if %r == "replace": cli_controls._fault = mutate
    try:
        return real_read(parent, name, path, maximum, modes=modes)
    finally:
        active = False
        cli_controls._fault = previous
cli_controls.read_control = read
os.close = close
''' % (str(target), fault, fault)
                with self.subTest(option=option, fault=fault):
                    self.diagnostic(self.invoke(self.arguments(command, **{option: target}),
                        prelude=prelude, expected=6), "integrity_error" if fault == "replace" else "operational_error")
                    self.assertFalse(self.destination.exists())
                    self.assertFalse(list(self.parent.glob(".readable-refresh-*")))

    def test_refresh_descriptor_admission_precedes_acquisition(self):
        """Independent adapter bounds reject before acquisitions and admit equality with all pins closed."""
        trace = self.parent / "admission-trace"
        prelude = '''
import atexit, json, os
from pathlib import Path
from research_pipeline import checkout, cli_views, view_refresh
from research_pipeline.cli_controls import CliError
from research_pipeline.store import RecordStore
real_limits, real_open, real_close = cli_views.read_readable_limits, checkout._Directories.open, os.close
real_store = RecordStore.open
active, events, held = False, [], {}
failure_path = None
def limits(*args, **kwargs):
    """Start acquisition accounting only after real bootstrap limits decoding and close."""
    global active
    result = real_limits(*args, **kwargs)
    active = True
    return result
def acquire(self, name, parent=None, **kwargs):
    """Record real adapter directory acquisitions without deduplicating shared ancestors."""
    if active: events.append(str(kwargs.get("path", name)))
    fd = real_open(self, name, parent, **kwargs)
    if active: held[fd] = str(kwargs.get("path", name))
    if active and held[fd] == failure_path:
        raise OSError(5, "preflight acquisition failure")
    return fd
def close(fd):
    """Track checked closure of every recorded preflight directory descriptor."""
    real_close(fd)
    held.pop(fd, None)
def store(*args, **kwargs):
    """Record store opening while retaining the real store and capture behavior."""
    events.append("store")
    return real_store(*args, **kwargs)
def delegated(*args, **kwargs):
    """Stop at real delegation without fabricating a successful library publication."""
    assert not held, held
    assert kwargs["absolute_path_maximum"] == 4096
    events.append("delegated")
    raise CliError(6, "operational_error", "Stopped at adapter delegation for boundary evidence.")
def finish():
    """Persist acquisition/closure evidence after CLI cleanup, even on admission failure."""
    Path(%r).write_text(json.dumps(dict(events=events, held=held)))
atexit.register(finish)
cli_views.read_readable_limits = limits
checkout._Directories.open = acquire
os.close = close
RecordStore.open = store
view_refresh._refresh_readable_view = delegated
''' % str(trace)
        # Each scenario makes a different simultaneous or sequential term dominant.
        for scenario in ("destination", "prior", "runtime", "baseline"):
            branch = self.parent / ("descriptor-" + scenario)
            branch.mkdir(mode=0o700)
            for index in range({"destination": 2, "prior": 5, "runtime": 10, "baseline": 28}[scenario]):
                branch = branch / ("level" + str(index))
                branch.mkdir(mode=0o700)
            if scenario == "destination":
                self.destination = branch / "output"
            elif scenario == "prior":
                import stat
                new = branch / "prior"
                prior_mode = stat.S_IMODE(self.view.stat().st_mode)
                # Cross-parent directory rename needs owner-write on the moved root;
                # this permission change is fixture preparation only.
                self.view.chmod(prior_mode | stat.S_IWUSR)
                try:
                    self.view.rename(new)
                    self.view = new
                finally:
                    self.view.chmod(prior_mode)
                self.assertEqual(stat.S_IMODE(self.view.stat().st_mode), prior_mode)
            elif scenario == "runtime":
                self.store.close()
                new = branch / "store"
                self.runtime.rename(new)
                self.runtime = new
                self.config = self.control("config", dict(format="research_pipeline.cli_config", version=1,
                    store=str(self.runtime), protected_roots=[]))
            else:
                new = branch / "baseline"
                self.baseline.rename(new)
                self.baseline = new
            b, d, p, r = (len(self.baseline.parent.parts), len(self.destination.parent.parts),
                           len(self.view.parts), len(self.runtime.parts))
            outer = 64 + 2 * max(b + 1, d + p + 1, d + r + 2)
            for nested, allowance, admitted in ((1, 4096, False), (4096, 1, False),
                    (p, 4096, False), (4096, outer - 1, False), (p + 1, outer, True)):
                with self.subTest(scenario=scenario, nested=nested, outer=allowance):
                    value = self.limit_value("refresh-readable-view")
                    value["refresh_limits"]["capture_limits"]["max_open_descriptors"] = nested
                    value["refresh_limits"]["max_open_descriptors"] = allowance
                    chosen = self.control("admission-limits", value)
                    self.diagnostic(self.invoke(self.arguments("refresh-readable-view", limits=chosen),
                        prelude=prelude, expected=6 if admitted else 5),
                        "operational_error" if admitted else "limit_exceeded")
                    evidence = json.loads(trace.read_text())
                    self.assertEqual(evidence["held"], {})
                    if admitted:
                        self.assertEqual(evidence["events"][-1], "delegated")
                        self.assertIn("store", evidence["events"])
                        for path in (self.baseline.parent, self.destination.parent, self.view, self.runtime):
                            self.assertIn(str(path), evidence["events"])
                    else:
                        self.assertEqual(evidence["events"], [])
                    self.assertFalse(self.destination.exists())
                    self.assertFalse(list(self.destination.parent.glob(".readable-refresh-*")))
        failed = prelude + "\nfailure_path = %r\n" % str(self.runtime / "objects")
        self.diagnostic(self.invoke(self.arguments("refresh-readable-view"), prelude=failed, expected=6),
                        "operational_error")
        evidence = json.loads(trace.read_text())
        self.assertIn(str(self.runtime / "objects"), evidence["events"])
        self.assertNotIn("store", evidence["events"])
        self.assertEqual(evidence["held"], {})
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.destination.parent.glob(".readable-refresh-*")))

    def long_output_parent(self, name, byte_length):
        """Build an existing private chain of exact UTF-8 length and register descriptor-relative cleanup."""
        root = self.parent / name
        root.mkdir(mode=0o700)
        self.addCleanup(self.remove_long_output, root)
        current = root
        while len(str(current).encode("utf-8")) < byte_length:
            remaining = byte_length - len(str(current).encode("utf-8"))
            size = min(200, remaining - 1)
            if remaining - size - 1 == 1:
                size -= 1
            self.assertGreater(size, 0)
            current = current / ("p" * size)
            current.mkdir(mode=0o700)
        self.assertEqual(len(str(current).encode("utf-8")), byte_length)
        return current

    def remove_long_output(self, root):
        """Remove only this synthetic long-path fixture through directory descriptors, including read-only output."""
        def empty(fd):
            """Make each owned fixture directory writable and remove its immediate descendants without long syscalls."""
            import stat
            os.fchmod(fd, 0o700)
            for name in os.listdir(fd):
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        empty(child)
                    finally:
                        os.close(child)
                    os.rmdir(name, dir_fd=fd)
                else:
                    os.unlink(name, dir_fd=fd)
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            empty(fd)
        finally:
            os.close(fd)
        root.rmdir()

    def read_long_output(self, root, relative):
        """Read a published boundary leaf through real descriptor-relative operations, avoiding host PATH_MAX."""
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            parts = Path(relative).parts
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                return os.read(leaf, 65536)
            finally:
                os.close(leaf)
        finally:
            os.close(fd)

    def test_refresh_complete_absolute_inventory_byte_boundaries(self):
        """Real refresh admits 4096-byte preserved paths and rejects 4097 before reserving either output root."""
        from research_pipeline.view_refresh import PACKAGE_PREFIX
        from tests.view_capture_fixtures import tree_state
        self.view.chmod(0o700)
        relative_parent = "/".join(("a" * 200, "b" * 200, "c" * 200))
        directory = self.view / relative_parent
        directory.mkdir(parents=True, mode=0o700)
        for parent in directory.parents:
            if parent == self.view:
                break
            parent.chmod(0o700)
        native = relative_parent + "/" + "é" * 90 + ".bin"
        payload = b"inert authored native bytes\x00\xff"
        self.write(native, payload)
        (directory / ("ø" * 92)).mkdir(mode=0o700)
        self.write("manifest.json", b"opaque edited historical control\n")
        self.write(self.plan.artifact_copies[0].relative_path, b"human artifact edit\n")
        self.rename("README.md", "renamed-reading.md")
        preserved = "preservation/tree/" + native
        self.assertLess(len(native.encode("utf-8")), 1000)
        prior_before = tree_state(self.view)
        baseline_before = self.baseline.read_bytes(), self.baseline.stat()
        for name in ("out", "destination-" + "d" * 100):
            for maximum in (4096, 4097):
                with self.subTest(name=name, maximum=maximum):
                    longest_root_name = max(len(name), len(PACKAGE_PREFIX) + 32)
                    parent_size = maximum - longest_root_name - len(preserved.encode("utf-8")) - 2
                    parent = self.long_output_parent("long-" + str(len(name)) + "-" + str(maximum), parent_size)
                    destination = parent / name
                    self.assertLess(len(str(destination).encode("utf-8")), 4096)
                    process = self.invoke(self.arguments("refresh-readable-view", destination=destination),
                                          expected=0 if maximum == 4096 else 5)
                    if maximum == 4096:
                        result = self.result(process)
                        self.assertEqual(self.read_long_output(destination, preserved), payload)
                        self.assertEqual(self.read_long_output(destination,
                            "preservation/controls/expected-manifest.json"), self.plan.manifest_bytes)
                        self.assertEqual(self.read_long_output(destination,
                            "preservation/controls/observed-manifest.bin"), b"opaque edited historical control\n")
                        manifest = json.loads(self.read_long_output(destination, "refresh.json"))
                        self.assertIn("preservation/tree/" + relative_parent + "/" + "ø" * 92,
                                      [row["path"] for row in manifest["directories"]])
                        self.assertEqual(result["successor_path"], str(destination / "generation"))
                        self.assertTrue(Path(result["attempt_path"]).is_dir())
                    else:
                        context = self.diagnostic(process, "limit_exceeded")
                        self.assertIsNone(context["attempt_path"])
                        self.assertEqual(list(parent.iterdir()), [])
                        # The unchanged public API retains its relative-path contract;
                        # descriptor-relative publication can exceed the CLI ceiling.
                        public = self.refresh(destination=destination)
                        self.assertEqual(public.destination, str(destination))
                        self.assertEqual(self.read_long_output(destination, preserved), payload)
                    self.assertEqual(tree_state(self.view), prior_before)
                    self.assertEqual(self.baseline.read_bytes(), baseline_before[0])
                    after = self.baseline.stat()
                    before = baseline_before[1]
                    self.assertEqual((after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                                     (before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns, before.st_ctime_ns))
