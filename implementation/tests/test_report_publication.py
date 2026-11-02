"""Exact historical report projection, offline navigation and explicit publication recovery."""

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_pipeline import reports, vault, report_capture
from research_pipeline.domain import ArtifactReference, DomainValidationError
from research_pipeline.snapshot import SnapshotLimits, SnapshotLimitError, DetachedSnapshot, _canonical
from research_pipeline.store import RecordStore
from research_pipeline.report_capture import prepare_report_view
from research_pipeline.reports import ReportRequest, ReportObservation
from research_pipeline.view_plan import readable_plan_from_manifest, verify_plan_links, ViewPlanError, plan_readable_snapshot, _snapshot_from_manifest
from research_pipeline.vault import materialize_readable_view, inspect_readable_publication, recover_readable_view, ViewError
from tests.report_fixtures import report_request, populate, ref, text
from tests.test_store import record, request
from tests.test_vault import child_environment, restore_directories
from tests.test_view_plan import forged_plan
from tests.view_capture_fixtures import tree_state, SOURCE


def report_limits():
    """Retain the same independent allowances as the report fixture's saved scientific capture."""
    return SnapshotLimits(**report_request().to_dict()["limits"]["snapshot"])


def navigation(root):
    """Resolve actual ordinary Markdown links, ignoring authored data inside inert literal blocks."""
    routes = {}
    manifest = json.loads((root / "manifest.json").read_bytes())
    pages = [root / row["path"] for row in manifest["files"]
             if row["hash_kind"] == "generated" and row["path"].endswith(".md")]
    pages.extend(root / "reports/runs" / item["observation"]["request"]["run"]["record_id"] /
                 str(item["observation"]["request"]["report_revision"]) / "report.md"
                 for item in manifest.get("reports", []))
    for page in pages:
        lines = [line for line in page.read_text().splitlines() if not line.startswith("    ")]
        targets = []
        for destination in re.findall(r"\[[^\[\]\n]*\]\(([^)]+)\)", "\n".join(lines)):
            target = (page.parent / destination.split("#")[0]).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise AssertionError(str(page) + " -> " + destination)
            targets.append(target)
        routes[page.resolve()] = targets
    return routes


class ReportViewFixture(unittest.TestCase):
    """Shared real SQLite/artifact setup; each concrete test owns an independent private tree."""

    def setUp(self):
        """Allocate a source store and retain cleanup for protected generation directories."""
        temporary = TemporaryDirectory(prefix="report-publication-")
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.addCleanup(restore_directories, self.parent)
        self.root = self.parent / "runtime"
        self.store = RecordStore.create(self.root)
        self.addCleanup(self.store.close)
        populate(self.store)
        self.limits = report_limits()

    def commit(self, identity="first", revision=1, **updates):
        """Commit a dated report and prepare its exact publication plan with independent allowances."""
        result = self.store.commit_report(report_request(identity, revision, **updates))
        return result, prepare_report_view(self.store, identity, limits=self.limits)

    def publish(self, plan, name="view"):
        """Use the actual protected materializer without changing path or integrity guards."""
        return materialize_readable_view(self.store, plan, self.parent / name,
            source_root=SOURCE, protected_roots=[], max_entries=10000)

    def arguments(self, plan):
        """Supply independent pinned plan and explicit offline exclusions for inspection/recovery."""
        return dict(expected_plan=plan, limits=self.limits, source_root=SOURCE,
                    protected_roots=[self.root], max_entries=10000)


class ReportProjectionTests(ReportViewFixture):
    """Pure projection verification remains independent of filesystem publication availability."""

    def test_historical_v1_bytes_and_mixed_baselines(self):
        """Retained accepted-source bytes protect old rendering and ordinary manifest interpretation."""
        fixture = json.loads((Path(__file__).parent / "fixtures/report_v1.json").read_bytes())
        data = fixture["objects"]["source.json"].encode("ascii")
        old = reports.loads_observation(data)
        self.assertEqual(old.to_dict()["version"], 1)
        self.assertEqual(reports.dumps_observation(old).encode("ascii"), data)
        for name, rendered in reports.render_report(old).items():
            self.assertEqual(rendered, fixture["objects"][name].encode("utf-8"))
        manifest = fixture["manifest"].encode("ascii")
        legacy = readable_plan_from_manifest(manifest, limits=self.limits)
        self.assertEqual(legacy.plan_id, "42977869b630498052a8d61ad42aaa90ba72ab8646a7ee1c9693b3c6fd1fd890")
        self.assertEqual(legacy.manifest_bytes, manifest)
        self.assertNotIn("reports", legacy.to_dict())
        self.assertNotIn(b"(README.md)", reports.render_report(old)["report.md"])
        # Install the historical submission through its exact existing storage contract.
        with RecordStore.create(self.parent / "historical") as store:
            with patch("research_pipeline.store.datetime") as clock:
                clock.now.return_value = datetime(2026, 11, 1, tzinfo=timezone.utc)
                populate(store)
                objects = {name: store.put_artifact(value.encode("utf-8")) for name, value in fixture["objects"].items()}
                receipt = store.submit(reports._submission(old.to_dict(), objects))
            self.assertEqual(receipt.to_dict(), fixture["result"]["receipt"])
            original = store.commit_report(report_request())
            self.assertEqual(original.to_dict(), fixture["result"])
            store.commit_report(report_request("mixed", 2, start_baseline=ref(reports.manifest_id("run"), "work_product_manifest", "start_baseline")))
            plan = prepare_report_view(store, "mixed", limits=self.limits)
            entries = plan.to_dict()["reports"]
            self.assertEqual([r["observation"]["version"] for r in entries], [1, 2])
            self.assertEqual(entries[1]["observation"]["baseline"]["observation"]["version"], 1)
            self.assertEqual(readable_plan_from_manifest(plan.manifest_bytes, limits=self.limits), plan)
            self.assertEqual(store.read_artifact(objects["report.md"]), fixture["objects"]["report.md"].encode("utf-8"))

    def test_exact_operation_after_later_writes_reopen_restore(self):
        """Preparation performs no capture/write and remains byte-identical after head advancement and restore."""
        from research_pipeline.backup import create_backup, restore_backup
        first, plan = self.commit()
        self.store.submit(request("later", [record("project", 2, kind="project")], {"project": 1}))
        self.commit("second", 2)
        with patch.object(self.store, "commit_report", side_effect=AssertionError("commit")), \
             patch.object(self.store, "capture_snapshot", side_effect=AssertionError("capture")), \
             patch.object(self.store, "inspect_resources", side_effect=AssertionError("resources")), \
             patch.object(self.store, "put_artifact", side_effect=AssertionError("write")):
            self.assertEqual(prepare_report_view(self.store, "first", limits=self.limits), plan)
        create_backup(self.store, self.parent / "backup")
        self.store.close()
        with RecordStore.open(self.root) as reopened:
            self.assertEqual(prepare_report_view(reopened, "first", limits=self.limits), plan)
            self.assertEqual(reopened.get_report_operation("first"), first)
        with restore_backup(self.parent / "backup", self.parent / "restored") as restored:
            self.assertEqual(prepare_report_view(restored, "first", limits=self.limits), plan)

    def test_closed_rehashed_descriptors_and_prose(self):
        """Recomputed descriptor hashes cannot legitimize invented bindings, omitted history or changed prose."""
        self.commit()
        _, plan = self.commit("second", 2)
        for mutation in ("selection", "omit", "duplicate", "receipt", "extra", "source"):
            value = plan.to_dict()
            if mutation == "selection":
                value["selected_report_operation_id"] = "first"
            elif mutation == "omit":
                value["reports"].pop(0)
            elif mutation == "duplicate":
                value["reports"][1] = value["reports"][0]
            elif mutation == "receipt":
                value["reports"][-1]["result"]["receipt"]["fingerprint"] = "0" * 64
            elif mutation == "extra":
                value["reports"][-1]["path"] = "caller-instruction"
            else:
                value["reports"][-1]["result"]["artifacts"]["source.json"]["digest"] = "0" * 64
            value["plan_id"] = hashlib.sha256(_canonical({k:v for k,v in value.items() if k != "plan_id"}).encode()).hexdigest()
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, DomainValidationError)):
                readable_plan_from_manifest(_canonical(value).encode(), limits=self.limits)
        forged = forged_plan(plan, {"README.md": b"# Forged prose\n"})
        with self.assertRaises(ViewPlanError):
            verify_plan_links(forged)
        duplicate = plan.manifest_bytes.replace(b'"selected_report_operation_id":', b'"selected_report_operation_id":"first","selected_report_operation_id":', 1)
        with self.assertRaises(ValueError):
            readable_plan_from_manifest(duplicate, limits=self.limits)

    def test_caller_bounds_before_object_reads_and_unsafe_run(self):
        """Bound declared source sizes before fetch; record-codec device names cannot become publication paths."""
        result, plan = self.commit()
        with patch.object(self.store, "read_artifact", side_effect=AssertionError("oversized fetch")):
            with self.assertRaises(SnapshotLimitError):
                prepare_report_view(self.store, "first", limits=replace(self.limits, max_file_bytes=1))
        for key in self.limits.to_dict():
            if getattr(self.limits, key):
                with self.subTest(key=key), self.assertRaises(SnapshotLimitError):
                    readable_plan_from_manifest(plan.manifest_bytes, limits=replace(self.limits, **{key:getattr(self.limits,key)-1}))
        self.store.submit(request("device-run", [record("CON", kind="run", record_references=[reports.RecordReference("project", 1, "project", "project")])]))
        unsafe = report_request("unsafe", run=ref("CON", "run", "run"))
        self.store.commit_report(unsafe)
        with self.assertRaises((DomainValidationError, ViewPlanError)):
            prepare_report_view(self.store, "unsafe", limits=self.limits)
        self.assertEqual(self.store.get_report_operation("first"), result)

    def test_report_source_damage_and_history_drop(self):
        """Damaged originals fail preparation while original-operation reconciliation remains available."""
        from research_pipeline.view_refresh_metadata import _relationships
        from research_pipeline.artifacts import ArtifactIntegrityError
        result, first = self.commit()
        _, second = self.commit("second", 2)
        _relationships(first, second, 10000)
        with self.assertRaises(vault.ViewIntegrityError):
            _relationships(second, first, 10000)
        legacy = plan_readable_snapshot(DetachedSnapshot(_snapshot_from_manifest(first.to_dict())))
        with self.assertRaises(vault.ViewIntegrityError):
            _relationships(first, legacy, 10000)
        source = self.root / "objects" / result.to_dict()["artifacts"]["source.json"]["digest"]
        source.chmod(0o600)
        source.write_bytes(b"corruption")
        with self.assertRaises(ArtifactIntegrityError):
            prepare_report_view(self.store, "second", limits=self.limits)
        self.assertEqual(self.store.get_report_operation("first"), result)


class ReportPublicationTests(ReportViewFixture):
    """Real protected output and retained attempt recovery without weakening source exclusion guards."""

    def test_home_report_navigation_offline_exact_bytes(self):
        """Read actual home/report/navigation/envelope/artifact routes with no open store or model."""
        artifact = self.store.put_artifact(b"negative saved observation")
        from tests.test_assessment_store import mixed_graph, declarations
        from research_pipeline.scientific import decode_envelope, encode_envelope
        from research_pipeline.work_product import encode_envelope as product_envelope
        from tests.test_work_product import manifest
        from tests.test_store import CREATOR
        self.store.submit(request("declarations", declarations()))
        graph = mixed_graph(artifact)
        for index, envelope in enumerate(graph):
            if envelope.kind == "evidence":
                graph[index] = encode_envelope(envelope.record_id, 1,
                    replace(decode_envelope(envelope), result="NEGATIVE result", origin="unverified"), CREATOR)
        self.store.submit_typed(request("science", graph))
        products = [product_envelope(kind, 1, replace(manifest(artifact), product_kind=kind), CREATOR)
                    for kind in ("derivation", "calculation", "checkpoint")]
        self.store.submit_typed(request("products", products))
        proposal = report_request(selection=[ref("review-a", "review"), ref("review-b", "review"), ref("issue", "issue"),
            *[ref(kind,"work_product_manifest") for kind in ("derivation", "calculation", "checkpoint")]]).to_dict()
        proposal["declarations"]["continuation"] = [dict(priority=1, task=ref("task", "task_specification", "task"),
            checkpoint=ref("checkpoint", "work_product_manifest", "checkpoint"), dependencies=[ref("evidence", "evidence")],
            expected_output=text("Saved output"), required_checks=text("Review"), required_authority=text(), required_resources=reports.unavailable("No estimate"))]
        self.store.commit_report(ReportRequest(proposal))
        first = prepare_report_view(self.store, "report_initial", limits=self.limits)
        result, plan = self.commit("later", 2)
        published = self.publish(plan)
        self.store.close()
        root = Path(published.destination)
        with patch("socket.socket", side_effect=AssertionError("network")), patch.object(RecordStore, "open", side_effect=AssertionError("store")):
            routes = navigation(root)
            home, report, adjacent = root / "README.md", root / "reports/runs/run/2/report.md", root / "reports/runs/run/2/README.md"
            self.assertIn(report.resolve(), routes[home.resolve()])
            self.assertIn(adjacent.resolve(), routes[report.resolve()])
            historical = root / "reports/runs/run/1/README.md"
            self.assertIn(historical.resolve(), routes[adjacent.resolve()])
            for item in plan.to_dict()["reports"]:
                base = root / "reports/runs/run" / str(item["observation"]["request"]["report_revision"])
                for name, expected in item["result"]["artifacts"].items():
                    data = (base / name).read_bytes()
                    self.assertEqual((hashlib.sha256(data).hexdigest(), len(data)), (expected["digest"], expected["size"]))
                self.assertTrue(any(p.name == "envelope.json" for p in routes[(base / "README.md").resolve()]))
            old_text = (root / "reports/runs/run/1/report.md").read_text()
            for phrase in ("NEGATIVE result", "disputed", "blocking", "Saved output"):
                self.assertIn(phrase, old_text)
            self.assertEqual(inspect_readable_publication(published.attempt_path, root, **self.arguments(plan)).status, "published")

    def test_interruptions_recover_original_after_newer_writes(self):
        """Each actual lifecycle boundary has truthful inspection and repeatable original-plan recovery."""
        result, plan = self.commit()
        for point in ("after_attempt_reservation", "after_generation_reservation", "after_intent", "after_file",
                      "after_ready", "before_rename", "after_rename", "after_publication_sync", "after_published"):
            with self.subTest(point=point):
                def fail(boundary):
                    """Lose acknowledgment after the selected real operation."""
                    if boundary == point:
                        raise KeyboardInterrupt(point)
                with patch.object(vault, "_fault", side_effect=fail), self.assertRaises(KeyboardInterrupt) as raised:
                    self.publish(plan, point)
                recovery = raised.exception._readable_recovery
                args = self.arguments(plan)
                inspection = inspect_readable_publication(recovery["attempt_path"], recovery["destination"], **args)
                self.assertEqual(inspection.historical_acknowledgment, "not_established")
                if point in ("after_attempt_reservation", "after_generation_reservation", "after_intent", "after_file"):
                    self.assertEqual(inspection.status, "incomplete_preparation")
                    before = tree_state(self.parent)
                    with self.assertRaises(ViewError):
                        recover_readable_view(recovery["attempt_path"], recovery["destination"], **args)
                    self.assertEqual(tree_state(self.parent), before)
                else:
                    self.assertEqual(inspection.status, "published" if point.startswith("after_") and point not in ("after_ready",) else "complete_unpublished")
                    recovered = recover_readable_view(recovery["attempt_path"], recovery["destination"], **args)
                    self.assertEqual(recovered.plan_id, plan.plan_id)
                    self.assertEqual(recover_readable_view(recovered.attempt_path, recovered.destination, **args), recovered)
        self.commit("newer", 2)
        self.store.close()
        recovered = recover_readable_view(recovered.attempt_path, recovered.destination, **args)
        self.assertEqual(recovered.plan_id, plan.plan_id)

    def test_complete_before_ready_and_actual_close_loss(self):
        """A complete protected payload can recover before ready; an actual closed fd failure stays uncertain."""
        _, plan = self.commit()
        original = vault._prepare_generation
        def prepared(*args, **kwargs):
            """Stop after the real complete protected generation but before the caller appends readiness."""
            original(*args, **kwargs)
            raise KeyboardInterrupt("complete before ready")
        with patch.object(vault, "_prepare_generation", side_effect=prepared), self.assertRaises(KeyboardInterrupt) as raised:
            self.publish(plan)
        info = raised.exception._readable_recovery
        args = self.arguments(plan)
        self.assertEqual(inspect_readable_publication(info["attempt_path"], info["destination"], **args).status, "complete_unpublished")
        original_close, triggered = os.close, []
        def close(fd):
            """Close the actual output inode, then lose its final acknowledgment after publication."""
            regular = stat.S_ISREG(os.fstat(fd).st_mode)
            original_close(fd)
            if regular and Path(info["destination"]).exists() and not triggered:
                triggered.append(True)
                raise OSError("actual checked-close loss")
        with patch("research_pipeline.vault.os.close", side_effect=close), self.assertRaises(vault.ViewOperationalError):
            recover_readable_view(info["attempt_path"], info["destination"], **args)
        self.assertTrue(triggered)
        self.assertEqual(inspect_readable_publication(info["attempt_path"], info["destination"], **args).status, "published")
        recover_readable_view(info["attempt_path"], info["destination"], **args)

    def test_recovery_rechecks_ancestor_layout_before_rename(self):
        """A new ancestor control marker prevents recovery without modifying the retained payload."""
        _, plan = self.commit()

        def interrupt(point):
            """Retain complete output before its exclusive rename."""
            if point == "before_rename":
                raise KeyboardInterrupt()

        with patch.object(vault, "_fault", side_effect=interrupt), self.assertRaises(KeyboardInterrupt) as raised:
            self.publish(plan)
        info = raised.exception._readable_recovery
        marker = self.parent / "manifest.json"

        def insert_marker(point):
            """Introduce a recognizable protected ancestor after the initial inspection."""
            if point == "before_rename":
                marker.write_bytes(b"external control")

        with patch.object(vault, "_fault", side_effect=insert_marker), self.assertRaises(ViewError):
            recover_readable_view(info["attempt_path"], info["destination"], **self.arguments(plan))
        self.assertFalse(Path(info["destination"]).exists())
        self.assertEqual(marker.read_bytes(), b"external control")
        marker.unlink()
        self.assertEqual(inspect_readable_publication(info["attempt_path"], info["destination"],
            **self.arguments(plan)).status, "complete_unpublished")

    def test_competitor_equal_bytes_tamper_and_unsafe_objects(self):
        """Equal bytes never substitute for attempt inode identity, and unsafe controls/output fail closed."""
        _, plan = self.commit()
        def fail(point):
            """Retain complete output at the exact pre-rename seam."""
            if point == "before_rename":
                raise KeyboardInterrupt()
        with patch.object(vault, "_fault", side_effect=fail), self.assertRaises(KeyboardInterrupt) as raised:
            self.publish(plan)
        info = raised.exception._readable_recovery
        self.publish(plan)  # Same bytes, independent destination inode and distinct attempt.
        args = self.arguments(plan)
        before = tree_state(self.parent)
        self.assertEqual(inspect_readable_publication(info["attempt_path"], info["destination"], **args).status, "competing_destination")
        with self.assertRaises(ViewError):
            recover_readable_view(info["attempt_path"], info["destination"], **args)
        self.assertEqual(tree_state(self.parent), before)
        marker = Path(info["attempt_path"]) / "ready.json"
        marker.chmod(0o600)
        marker.write_bytes(b'{}')
        marker.chmod(0o400)
        self.assertEqual(inspect_readable_publication(info["attempt_path"], info["destination"], **args).status, "inconsistent")
        for kind in ("hardlink", "symlink", "mode", "bytes"):
            published = self.publish(plan, kind)
            root = Path(published.destination)
            file = root / "reports/runs/run/1/report.md"
            file.parent.chmod(0o700)
            if kind == "hardlink":
                os.link(file, self.parent / "extra-link")
            elif kind == "symlink":
                file.unlink(); file.symlink_to(self.parent / "missing")
            else:
                file.chmod(0o600)
                if kind == "bytes":
                    file.write_bytes(b"changed"); file.chmod(0o400)
            file.parent.chmod(0o500)
            with self.subTest(kind=kind), self.assertRaises(ViewError):
                recover_readable_view(published.attempt_path, root, **args)

    def test_write_sync_and_unavailable_destination_keep_source_identity(self):
        """Real I/O failures retain pending evidence and the committed result, never report successful publication."""
        import errno
        result, plan = self.commit()
        for failure in ("write", "fsync"):
            triggered = []
            original = os.write if failure == "write" else os.fsync
            def fail(fd, *args):
                """Fail one actual file operation with ENOSPC, preserving all retained partial bytes."""
                if stat.S_ISREG(os.fstat(fd).st_mode) and not triggered:
                    triggered.append(True)
                    raise OSError(errno.ENOSPC, "synthetic full disk")
                return original(fd, *args)
            with patch("research_pipeline.vault.os." + failure, side_effect=fail), self.assertRaises(ViewError) as raised:
                self.publish(plan, failure)
            self.assertTrue(triggered)
            info = raised.exception._readable_recovery
            self.assertFalse(Path(info["destination"]).exists())
            observed = inspect_readable_publication(info["attempt_path"],info["destination"],**self.arguments(plan))
            self.assertIn(observed.status,("incomplete_preparation","inconsistent"))
            with self.assertRaises(ViewError):
                recover_readable_view(info["attempt_path"],info["destination"],**self.arguments(plan))
            self.assertEqual(self.store.get_report_operation("first"),result)
        destination = self.parent / "occupied"
        destination.mkdir(mode=0o700)
        (destination/"human.txt").write_bytes(b"Keep this destination")
        before = tree_state(destination)
        with self.assertRaises(ViewError) as raised:
            self.publish(plan,"occupied")
        self.assertEqual(raised.exception._readable_recovery["plan_id"],plan.plan_id)
        self.assertEqual(tree_state(destination),before)
        self.assertEqual(self.store.get_report_operation("first"),result)

    def test_changed_source_binding_blocks_publication_but_complete_copy_recovers(self):
        """The materializer checks source integrity; offline recovery later needs only the exact complete copies."""
        result, plan = self.commit()
        digest = result.to_dict()["artifacts"]["report.md"]["digest"]
        source = self.root / "objects" / digest
        def replace_source(point):
            """Replace one actual canonical object binding after all copied output has been verified."""
            if point == "before_rename":
                source.rename(source.with_name("retained-" + digest))
                source.write_bytes(b"damaged replacement")
                source.chmod(0o400)
        with patch.object(vault,"_fault",side_effect=replace_source), self.assertRaises(ViewError) as raised:
            self.publish(plan)
        info=raised.exception._readable_recovery
        self.assertFalse(Path(info["destination"]).exists())
        self.store.close()
        args=self.arguments(plan)
        self.assertEqual(inspect_readable_publication(info["attempt_path"],info["destination"],**args).status,"complete_unpublished")
        recovered=recover_readable_view(info["attempt_path"],info["destination"],**args)
        copied=Path(recovered.destination)/"reports/runs/run/1/report.md"
        self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(),digest)

    def test_real_process_exit_and_competing_publishers(self):
        """Use pipe-synchronized independent publishers and abrupt exits, never sleep-based race evidence."""
        _, plan = self.commit()
        saved = self.parent / "pinned-plan.json"
        saved.write_bytes(plan.manifest_bytes)
        program = '''
import os,sys,json
from pathlib import Path
from research_pipeline import vault
from research_pipeline.store import RecordStore
from research_pipeline.snapshot import SnapshotLimits
from research_pipeline.view_plan import readable_plan_from_manifest
plan=readable_plan_from_manifest(Path(sys.argv[2]).read_bytes(),limits=SnapshotLimits(**json.loads(sys.argv[3])))
def seam(point):
    """Signal after readiness and await the parent before entering actual no-replace publication."""
    if point==sys.argv[6]:
        if sys.argv[7]=='exit': os._exit(73)
        os.write(int(sys.argv[7]),b'R')
        assert os.read(int(sys.argv[8]),1)==b'G'
vault._fault=seam
with RecordStore.open(sys.argv[1]) as store:
    vault.materialize_readable_view(store,plan,sys.argv[4],source_root=sys.argv[5],protected_roots=[],max_entries=10000)
'''
        for point in ("after_intent", "after_ready", "after_rename", "after_publication_sync", "after_published"):
            destination = self.parent / ("exit-" + point)
            before = set(self.parent.glob(".readable-view-*"))
            process = subprocess.run([sys.executable,"-B","-c",program,str(self.root),str(saved),json.dumps(self.limits.to_dict()),
                str(destination),str(SOURCE),point,"exit"],env=child_environment(),capture_output=True,timeout=30)
            self.assertEqual(process.returncode,73,process.stderr)
            attempt = (set(self.parent.glob(".readable-view-*")) - before).pop()
            observed = inspect_readable_publication(attempt,destination,**self.arguments(plan))
            if point == "after_intent":
                self.assertEqual(observed.status,"incomplete_preparation")
            else:
                recover_readable_view(attempt,destination,**self.arguments(plan))
        children, pipes = [], []
        destination = self.parent / "race"
        try:
            for index in range(2):
                ready_r,ready_w=os.pipe(); go_r,go_w=os.pipe()
                pipes.extend([ready_r,ready_w,go_r,go_w])
                child=subprocess.Popen([sys.executable,"-B","-c",program,str(self.root),str(saved),json.dumps(self.limits.to_dict()),
                    str(destination),str(SOURCE),"before_rename",str(ready_w),str(go_r)],env=child_environment(),
                    pass_fds=(ready_w,go_r),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                children.append((child,ready_r,go_w))
            import select
            for child,ready,go in children:
                self.assertTrue(select.select([ready],[],[],20)[0])
                self.assertEqual(os.read(ready,1),b'R')
            for child,ready,go in children:
                os.write(go,b'G')
            results=[]
            for child,_,_ in children:
                child.communicate(timeout=30);results.append(child.returncode)
            self.assertEqual(sorted(code==0 for code in results),[False,True])
            self.assertEqual(vault.inspect_readable_view(destination,limits=self.limits,max_entries=10000).status,"verified")
        finally:
            for child,_,_ in children:
                if child.poll() is None:
                    child.kill();child.wait()
            for fd in pipes:
                os.close(fd)


class ReportRefreshTests(ReportViewFixture):
    """Retained report history and direct edit preservation through offline interrupted refresh recovery."""

    def refresh_limits(self):
        """Use the established package fixture with independent allowances covering retained report limits."""
        from tests.view_refresh_fixtures import refresh_limits
        from tests.view_capture_fixtures import capture_limits
        return refresh_limits(capture_limits=capture_limits(plan_limits=self.limits,
            max_entries=10000, max_files=5000, max_directories=5000,
            max_file_bytes=60_000_000, max_total_bytes=200_000_000, max_metadata_bytes=200_000_000),
            successor_limits=self.limits)

    def test_v1_to_v2_and_report_history_retention(self):
        """A legacy readable generation refreshes to explicit reports; report bindings can never be dropped."""
        from research_pipeline.view_refresh import refresh_readable_view, inspect_readable_refresh
        _, plan = self.commit()
        legacy = plan_readable_snapshot(DetachedSnapshot(_snapshot_from_manifest(plan.to_dict())))
        prior = self.publish(legacy)
        result = refresh_readable_view(self.store, prior.destination, self.parent / "refreshed",
            expected_plan=legacy, new_plan=plan, source_root=SOURCE, protected_roots=[], limits=self.refresh_limits())
        self.assertEqual(inspect_readable_refresh(result.attempt_path,result.destination,
            source_root=SOURCE,protected_roots=[self.root],limits=self.refresh_limits()).status,"published")
        navigation(Path(result.successor_path))
        with self.assertRaises(vault.ViewIntegrityError):
            refresh_readable_view(self.store,result.successor_path,self.parent / "drop",
                expected_plan=plan,new_plan=legacy,source_root=SOURCE,protected_roots=[],limits=self.refresh_limits())
        self.assertFalse((self.parent / "drop").exists())

    def test_edited_renamed_report_files_offline_refresh_recovery(self):
        """Recover the frozen preservation payload after later prior edits without silently recapturing them."""
        from research_pipeline import view_refresh
        from research_pipeline.view_refresh import refresh_readable_view, inspect_readable_refresh, recover_readable_refresh
        first, _ = self.commit()
        _, prior_plan = self.commit("second",2)
        prior = Path(self.publish(prior_plan).destination)
        _, successor = self.commit("third",3)
        changed = {}
        for name in ("report.md", "source.json", "continuation.json"):
            old = prior / "reports/runs/run/2" / name
            old.parent.chmod(0o700)
            renamed = old.with_name("edited-" + name)
            old.rename(renamed)
            renamed.chmod(0o600)
            data = ("Human proposed " + name + "\n").encode()
            renamed.write_bytes(data)
            changed[str(renamed.relative_to(prior))] = data
        prior.chmod(0o700)
        (prior / "README.md").chmod(0o600)
        (prior / "README.md").write_bytes(b"Human home edit\n")
        changed["README.md"] = b"Human home edit\n"
        # Report 1 occurs both as a work-product copy and reserved report copy.
        duplicate = prior / "reports/runs/run/1/report.md"
        duplicate.parent.chmod(0o700)
        duplicate.rename(duplicate.with_name("moved-report.md"))
        before = tree_state(prior)
        def fail(point):
            """Interrupt only after the complete package has been copied and protected."""
            if point == "after_complete_package":
                raise KeyboardInterrupt()
        with patch.object(view_refresh,"_fault",side_effect=fail), self.assertRaises(KeyboardInterrupt) as raised:
            refresh_readable_view(self.store,prior,self.parent / "successor",expected_plan=prior_plan,new_plan=successor,
                source_root=SOURCE,protected_roots=[],limits=self.refresh_limits())
        info = raised.exception._readable_recovery
        args = dict(source_root=SOURCE,protected_roots=[self.root],limits=self.refresh_limits(),expected_refresh_id=info["refresh_id"])
        inspection = inspect_readable_refresh(info["attempt_path"],info["destination"],**args)
        self.assertEqual(inspection.status,"complete_unpublished")
        self.assertEqual(tree_state(prior),before)
        (prior / "README.md").write_bytes(b"Later edit must not replace saved preservation\n")
        for item in prior_plan.to_dict()["reports"]:
            for name, artifact in item["result"]["artifacts"].items():
                self.assertEqual(hashlib.sha256(self.store.read_artifact(ArtifactReference.from_dict(artifact))).hexdigest(),artifact["digest"])
        self.store.close()
        with patch.object(RecordStore,"open",side_effect=AssertionError("live source")):
            result = recover_readable_refresh(info["attempt_path"],info["destination"],**args)
            self.assertEqual(recover_readable_refresh(info["attempt_path"],info["destination"],**args),result)
            self.assertEqual(inspect_readable_refresh(info["attempt_path"],info["destination"],**args).status,"published")
        for name,data in changed.items():
            self.assertEqual((Path(result.preservation_path)/"tree"/name).read_bytes(),data)
        preservation=json.loads((Path(result.destination)/"preservation-plan.json").read_bytes())
        self.assertTrue(any(group["ambiguous"] for group in preservation["rename_groups"]))
        retained=json.loads((Path(result.preservation_path)/"controls/expected-manifest.json").read_bytes())
        report_mappings=[m for m in retained["mappings"] if m["logical_key"]["role"]=="committed_report_file"]
        self.assertEqual(len(report_mappings),6)
        self.assertTrue(all(m["logical_key"]["record_id"]==reports.manifest_id("run") for m in report_mappings))
        self.assertEqual((prior/"README.md").read_bytes(),b"Later edit must not replace saved preservation\n")
        navigation(Path(result.successor_path))
        for revision in (1,2,3):
            self.assertTrue((Path(result.successor_path)/"reports/runs/run"/str(revision)/"report.md").is_file())

    def test_refresh_recovery_rechecks_ancestor_layout(self):
        """Recovery rejects new ancestor controls without publishing or recapturing the frozen package."""
        from research_pipeline import view_refresh
        _, plan = self.commit()
        prior = self.publish(plan)

        def interrupt(point):
            """Retain a complete refresh package before publication."""
            if point == "after_complete_package":
                raise KeyboardInterrupt()

        with patch.object(view_refresh, "_fault", side_effect=interrupt), self.assertRaises(KeyboardInterrupt) as raised:
            view_refresh.refresh_readable_view(self.store, prior.destination, self.parent / "successor",
                expected_plan=plan, new_plan=plan, source_root=SOURCE, protected_roots=[], limits=self.refresh_limits())
        info = raised.exception._readable_recovery
        marker = self.parent / "manifest.json"

        def insert_marker(point):
            """Change the ancestor's layout at the final pre-rename boundary."""
            if point == "before_rename":
                marker.write_bytes(b"external control")

        args = dict(source_root=SOURCE, protected_roots=[self.root], limits=self.refresh_limits())
        with patch.object(view_refresh, "_fault", side_effect=insert_marker), self.assertRaises(ViewError):
            view_refresh.recover_readable_refresh(info["attempt_path"], info["destination"], **args)
        self.assertFalse(Path(info["destination"]).exists())
        self.assertEqual(marker.read_bytes(), b"external control")
        marker.unlink()
        self.assertEqual(view_refresh.inspect_readable_refresh(info["attempt_path"], info["destination"],
            **args).status, "complete_unpublished")

    def test_refresh_process_exit_retains_original_package(self):
        """Abrupt independent-process loss leaves a recoverable package without reopening canonical storage."""
        from research_pipeline.view_refresh import inspect_readable_refresh, recover_readable_refresh
        _, plan = self.commit()
        prior = self.publish(plan)
        pinned = self.parent / "refresh-plan.json"
        pinned.write_bytes(plan.manifest_bytes)
        program = '''
import os,sys
from pathlib import Path
from research_pipeline import view_refresh
from research_pipeline.store import RecordStore
from research_pipeline.view_plan import readable_plan_from_manifest
from tests.test_report_publication import report_limits
from tests.view_refresh_fixtures import refresh_limits
from tests.view_capture_fixtures import capture_limits
plan=readable_plan_from_manifest(Path(sys.argv[2]).read_bytes(),limits=report_limits())
limits=refresh_limits(capture_limits=capture_limits(plan_limits=report_limits(),max_entries=10000,max_files=5000,
    max_directories=5000,max_file_bytes=60000000,max_total_bytes=200000000,max_metadata_bytes=200000000),successor_limits=report_limits())
def crash(point):
    """Exit at the real complete-package or publication seam without cleanup."""
    if point==sys.argv[6]: os._exit(76)
view_refresh._fault=crash
with RecordStore.open(sys.argv[1]) as store:
    view_refresh.refresh_readable_view(store,sys.argv[3],sys.argv[4],expected_plan=plan,new_plan=plan,
        source_root=sys.argv[5],protected_roots=[],limits=limits)
'''
        for point in ("after_complete_package","after_rename","after_publication_sync","after_published"):
            destination=self.parent / ("refresh-exit-"+point)
            before=set(self.parent.glob(".readable-refresh-attempt-*"))
            process=subprocess.run([sys.executable,"-B","-c",program,str(self.root),str(pinned),prior.destination,
                str(destination),str(SOURCE),point],env=child_environment(),capture_output=True,timeout=60)
            self.assertEqual(process.returncode,76,process.stderr)
            attempt=(set(self.parent.glob(".readable-refresh-attempt-*"))-before).pop()
            args=dict(source_root=SOURCE,protected_roots=[self.root],limits=self.refresh_limits())
            observed=inspect_readable_refresh(attempt,destination,**args)
            self.assertEqual(observed.status,"complete_unpublished" if point=="after_complete_package" else "published")
            with patch.object(RecordStore,"open",side_effect=AssertionError("source access")):
                recovered=recover_readable_refresh(attempt,destination,expected_refresh_id=observed.refresh_id,**args)
                self.assertEqual(recover_readable_refresh(attempt,destination,expected_refresh_id=observed.refresh_id,**args),recovered)
            self.assertEqual(recovered.successor_plan_id,plan.plan_id)


class ReportMetadataBoundsTests(ReportViewFixture):
    """Corrupt actual SQLite rows and prove preparation rejects before unbounded reconstruction."""

    def setUp(self):
        """Commit and successfully prepare with the independently specified million-byte bounds."""
        super().setUp()
        self.limits = replace(self.limits, max_metadata_bytes=1_000_000, max_record_bytes=1_000_000)
        proposal = report_request("first").to_dict()
        proposal["limits"]["snapshot"] = self.limits.to_dict()
        self.result = self.store.commit_report(ReportRequest(proposal))
        self.plan = prepare_report_view(self.store, "first", limits=self.limits)
        self.event = self.result.to_dict()["source_event"]["record_id"]
        self.manifest = self.result.to_dict()["report_manifest"]["record_id"]

    def reject_unchanged(self, error=SnapshotLimitError, *, envelope=None, receipt=None,
                         operation="first", limits=None):
        """Check real post-corruption bytes/inventory, selectively forbidding premature readers.

        The corruption is already committed before the comparison. Decoder guards
        catch oversized JSON even if a later fingerprint check would reject it.
        """
        before = tree_state(self.parent)
        original_envelope = self.store._metadata_envelope
        original_receipt = self.store._receipt
        original_loads = json.loads

        def read_envelope(connection, identity, revision):
            """Allow unrelated historical reads but fail if the poisoned envelope is reconstructed."""
            if identity == envelope:
                raise AssertionError("actual oversized envelope reached reconstruction")
            return original_envelope(connection, identity, revision)

        def read_receipt(connection, identity):
            """Detect audit or membership reconstruction before its preflight succeeds."""
            if identity == receipt:
                raise AssertionError("actual poisoned receipt reached reconstruction")
            return original_receipt(connection, identity)

        def decode(value, *args, **kwargs):
            """Reject premature decoding by actual UTF-8 bytes, including multibyte corruption."""
            size = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
            if size > 1_000_000:
                raise AssertionError("oversized stored value reached JSON decoding")
            return original_loads(value, *args, **kwargs)

        try:
            with patch.object(self.store, "_metadata_envelope", side_effect=read_envelope), \
                    patch.object(self.store, "_receipt", side_effect=read_receipt), \
                    patch("json.loads", side_effect=decode), self.assertRaises(error):
                prepare_report_view(self.store, operation, limits=limits or self.limits)
        finally:
            self.assertEqual(tree_state(self.parent), before)

    def test_actual_revision_content_and_provenance_preflight(self):
        """Both report revisions reject the documented 2,000,014 bytes before any JSON reader."""
        oversized = '{"padding":"' + 'x' * 2_000_000 + '"}'
        self.assertEqual(len(oversized.encode()), 2_000_014)
        for identity in (self.event, self.manifest):
            for column in ("content_json", "provenance_json"):
                with self.subTest(identity=identity, column=column):
                    old = self.store._connection.execute("SELECT " + column + " FROM revisions WHERE record_id=?",
                                                         (identity,)).fetchone()[0]
                    self.store._connection.execute("UPDATE revisions SET " + column + "=? WHERE record_id=?",
                                                   (oversized, identity))
                    self.reject_unchanged(envelope=identity)
                    self.store._connection.execute("UPDATE revisions SET " + column + "=? WHERE record_id=?", (old, identity))

    def test_original_request_and_audit_preflight(self):
        """Bound original submission JSON before decoding and audit provenance before _receipt."""
        oversized = '{"padding":"' + 'x' * 2_000_000 + '"}'
        for table, column in (("submissions", "request_json"), ("audit_events", "provenance_json"),
                              ("audit_events", "committed_at"), ("submissions", "fingerprint")):
            with self.subTest(table=table, column=column):
                old = self.store._connection.execute("SELECT " + column + " FROM " + table + " WHERE submission_id='first'").fetchone()[0]
                self.store._connection.execute("UPDATE " + table + " SET " + column + "=? WHERE submission_id='first'", (oversized,))
                self.reject_unchanged(receipt="first")
                self.store._connection.execute("UPDATE " + table + " SET " + column + "=? WHERE submission_id='first'", (old,))

    def test_actual_link_fields_and_utf8_preflight(self):
        """Correct counts cannot hide oversized link fields; SQLite BLOB lengths count UTF-8 bytes."""
        self.store._connection.execute("PRAGMA foreign_keys=OFF")
        self.store._connection.execute("PRAGMA ignore_check_constraints=ON")
        for table, column in (("record_links", "relationship"), ("record_links", "target_id"),
                              ("record_links", "target_kind"), ("artifact_links", "digest")):
            with self.subTest(table=table, column=column):
                old = self.store._connection.execute("SELECT " + column + " FROM " + table + " WHERE record_id=? AND ordinal=0", (self.event,)).fetchone()[0]
                count = self.store._connection.execute("SELECT count(*) FROM " + table + " WHERE record_id=?", (self.event,)).fetchone()[0]
                self.store._connection.execute("UPDATE " + table + " SET " + column + "=? WHERE record_id=? AND ordinal=0", ("é" * 600_000, self.event))
                self.assertEqual(self.store._connection.execute("SELECT count(*) FROM " + table + " WHERE record_id=?", (self.event,)).fetchone()[0], count)
                self.reject_unchanged(envelope=self.event)
                self.store._connection.execute("UPDATE " + table + " SET " + column + "=? WHERE record_id=? AND ordinal=0", (old, self.event))

    def test_link_counts_and_receipt_membership_preflight(self):
        """Excessive link occurrences and non-two-member receipts fail before tuple construction."""
        connection = self.store._connection
        connection.execute("INSERT INTO record_links SELECT record_id,revision,999,relationship,target_id,target_revision,target_kind "
                           "FROM record_links WHERE record_id=? AND ordinal=0", (self.event,))
        self.reject_unchanged(reports.ReportIntegrityError, envelope=self.event)
        connection.execute("DELETE FROM record_links WHERE record_id=? AND ordinal=999", (self.event,))
        connection.executemany("INSERT INTO record_links VALUES (?,1,?,'extra','project',1,'project')",
                               ((self.event, ordinal) for ordinal in range(100, 10_100)))
        self.reject_unchanged(envelope=self.event)
        connection.execute("DELETE FROM record_links WHERE record_id=? AND ordinal>=100", (self.event,))
        connection.execute("UPDATE revisions SET submission_id='first',ordinal=2 WHERE record_id='project'")
        self.reject_unchanged(reports.ReportIntegrityError, receipt="first")

    def test_missing_membership_and_noncontiguous_ordinals(self):
        """Missing joins and malformed or gapped ordinals never reach receipt/envelope reconstruction."""
        connection = self.store._connection
        connection.execute("PRAGMA ignore_check_constraints=ON")
        for table, where, arguments, guarded in (
                ("revisions", "submission_id='first' AND ordinal=1", (), "receipt"),
                ("record_links", "record_id=? AND ordinal=0", (self.event,), "envelope"),
                ("artifact_links", "record_id=? AND ordinal=0", (self.event,), "envelope")):
            for ordinal in (999, "not-an-integer", -1):
                with self.subTest(table=table, ordinal=ordinal):
                    old = 1 if table == "revisions" else 0
                    connection.execute("UPDATE " + table + " SET ordinal=? WHERE " + where, (ordinal, *arguments))
                    self.reject_unchanged(reports.ReportIntegrityError, **{guarded: "first" if guarded == "receipt" else self.event})
                    connection.execute("UPDATE " + table + " SET ordinal=? WHERE ordinal=?", (old, ordinal))
        connection.execute("DELETE FROM audit_events WHERE submission_id='first'")
        self.reject_unchanged(reports.ReportIntegrityError, receipt="first")

    def test_remaining_aggregate_allowance_precedes_decoding(self):
        """Individually fitting raw content and provenance cannot overrun the shared remaining bytes."""
        connection = self.store._connection
        # Each field and the owning record fit one million bytes. Their rereads
        # plus previously retained request/receipt metadata exceed that allowance.
        for column in ("content_json", "provenance_json"):
            connection.execute("UPDATE revisions SET " + column + "=? WHERE record_id=?",
                               ('{"padding":"' + 'x' * 300_000 + '"}', self.event))
        self.reject_unchanged(envelope=self.event)

    def test_within_budget_corruption_still_checks_integrity(self):
        """Bounds supplement fingerprint, canonical JSON and exact binding validation."""
        connection = self.store._connection
        connection.execute("UPDATE submissions SET fingerprint=? WHERE submission_id='first'", ("0" * 64,))
        self.reject_unchanged(reports.ReportIntegrityError)
        connection.execute("UPDATE submissions SET fingerprint=? WHERE submission_id='first'", (self.result.receipt.fingerprint,))
        connection.execute("UPDATE revisions SET content_json='{}' WHERE record_id=?", (self.event,))
        self.reject_unchanged(reports.ReportIntegrityError)

    def test_source_binding_scalar_and_original_text_preflight(self):
        """Verification of pre-report scientific members shares the same preparation allowance."""
        connection = self.store._connection
        for table, column in (("submissions", "request_json"), ("audit_events", "provenance_json"),
                              ("audit_events", "committed_at"), ("submissions", "fingerprint")):
            with self.subTest(table=table, column=column):
                old = connection.execute("SELECT " + column + " FROM " + table + " WHERE submission_id='report_scopes'").fetchone()[0]
                connection.execute("UPDATE " + table + " SET " + column + "=? WHERE submission_id='report_scopes'", ("x" * 1_000_001,))
                self.reject_unchanged()
                connection.execute("UPDATE " + table + " SET " + column + "=? WHERE submission_id='report_scopes'", (old,))

    def test_maximum_depth_provenance_prepares(self):
        """Publication retains the supported request/result provenance depth without tighter snapshot reconstruction."""
        from tests.test_reports import boundary_request
        proposal = boundary_request().to_dict()
        proposal.update(operation_id="deep", report_revision=2)
        proposal["limits"]["snapshot"] = self.limits.to_dict()
        result = self.store.commit_report(ReportRequest(proposal))
        plan = prepare_report_view(self.store, "deep", limits=self.limits)
        self.assertEqual(plan.to_dict()["reports"][-1]["result"], result.to_dict())

    def test_budget_is_not_reset_for_later_history_member(self):
        """A field fitting a fresh budget fails against remaining bytes at the older chain member."""
        proposal = report_request("second", 2).to_dict()
        proposal["limits"]["snapshot"] = self.limits.to_dict()
        self.store.commit_report(ReportRequest(proposal))
        original = report_capture._preflight_revision
        used = []

        def observe(connection, expected, limits, budget, references):
            """Observe actual reservations when descending to the first committed report."""
            if expected.record_id == self.event:
                used.append(budget.used)
            return original(connection, expected, limits, budget, references)

        with patch.object(report_capture, "_preflight_revision", side_effect=observe):
            prepare_report_view(self.store, "second", limits=self.limits)
        self.assertEqual(len(used), 1)
        self.assertGreater(used[0], 0)
        size = (self.limits.max_metadata_bytes - used[0]) // 2 + 1
        self.assertLess(2 * size, self.limits.max_metadata_bytes)
        text = '{"padding":"' + 'x' * (size - 14) + '"}'
        self.store._connection.execute("UPDATE revisions SET content_json=? WHERE record_id=?", (text, self.event))
        self.reject_unchanged(envelope=self.event, operation="second")

    def test_exact_actual_metadata_record_and_reference_boundaries(self):
        """Actual preflight accounting accepts exact equality and rejects the adjacent smaller allowance."""
        from research_pipeline.view_capture import _Metadata
        connection = self.store._connection
        original = report_capture._metadata(self.store, connection, "first")
        records = original[2].records
        record_limit = max(len(_canonical(record.to_dict())) for record in records)
        references = sum(len(record.record_references) + len(record.artifact_references) for record in records)
        bounds = replace(self.limits, max_record_bytes=record_limit)
        budget = _Metadata(self.limits.max_metadata_bytes)
        remaining = [references]
        with self.store._transaction() as connection:
            actual = report_capture._metadata(self.store, connection, "first", preparation_limits=bounds,
                preparation_budget=budget, remaining_references=remaining)
        self.assertEqual(actual, original)
        self.assertEqual(remaining, [0])
        before = tree_state(self.parent)
        for byte_delta, record_delta, reference_delta in ((0, 0, 0), (-1, 0, 0), (0, -1, 0), (0, 0, -1)):
            with self.subTest(bytes=byte_delta, record=record_delta, references=reference_delta):
                def reconstruct():
                    """Exercise the preparation metadata reader with its independently measured exact limits."""
                    with self.store._transaction() as connection:
                        return report_capture._metadata(self.store, connection, "first",
                            preparation_limits=replace(bounds, max_record_bytes=record_limit + record_delta),
                            preparation_budget=_Metadata(budget.used + byte_delta),
                            remaining_references=[references + reference_delta])
                if byte_delta or record_delta or reference_delta:
                    with self.assertRaises(SnapshotLimitError):
                        reconstruct()
                else:
                    self.assertEqual(reconstruct(), original)
                self.assertEqual(tree_state(self.parent), before)

    def test_independent_record_budget_includes_links(self):
        """A generous aggregate allowance cannot override the owning record's combined byte ceiling."""
        connection = self.store._connection
        connection.execute("UPDATE record_links SET relationship=? WHERE record_id=?", ("x" * 350_000, self.event))
        self.assertEqual(connection.execute("SELECT count(*) FROM record_links WHERE record_id=?", (self.event,)).fetchone()[0], 3)
        self.reject_unchanged(envelope=self.event, limits=replace(self.limits, max_metadata_bytes=4_000_000))

    def test_malformed_storage_types_and_missing_revision_join(self):
        """Length preflights reject BLOB JSON, noninteger targets and missing identity joins as integrity errors."""
        connection = self.store._connection
        connection.execute("PRAGMA foreign_keys=OFF")
        for table, column, value in (("revisions", "content_json", b'{}'),
                                     ("record_links", "target_revision", "not-an-integer"),
                                     ("artifact_links", "size", "not-an-integer")):
            with self.subTest(table=table, column=column):
                old = connection.execute("SELECT " + column + " FROM " + table + " WHERE record_id=? AND "
                                         + ("revision=1" if table == "revisions" else "ordinal=0"), (self.event,)).fetchone()[0]
                where = " WHERE record_id=? AND " + ("revision=1" if table == "revisions" else "ordinal=0")
                connection.execute("UPDATE " + table + " SET " + column + "=?" + where, (value, self.event))
                self.reject_unchanged(reports.ReportIntegrityError, envelope=self.event)
                connection.execute("UPDATE " + table + " SET " + column + "=?" + where, (old, self.event))
        connection.execute("DELETE FROM identities WHERE record_id=?", (self.event,))
        self.reject_unchanged(reports.ReportIntegrityError, receipt="first")

    def test_oversized_binding_submission_identity(self):
        """Even joined scientific submission identifiers are bounded before loading and comparing their values."""
        connection = self.store._connection
        connection.execute("PRAGMA foreign_keys=OFF")
        identity = "s" * 1_000_001
        for table in ("revisions", "audit_events", "submissions"):
            connection.execute("UPDATE " + table + " SET submission_id=? WHERE submission_id='report_scopes'", (identity,))
        self.reject_unchanged()

    def test_within_budget_duplicate_json_rejected(self):
        """Strict canonical validation still rejects duplicated fields after successful byte preflight."""
        connection = self.store._connection
        for table, column, where, arguments in (
                ("revisions", "content_json", "record_id=?", (self.event,)),
                ("audit_events", "provenance_json", "submission_id='first'", ())):
            with self.subTest(table=table):
                old = connection.execute("SELECT " + column + " FROM " + table + " WHERE " + where, arguments).fetchone()[0]
                connection.execute("UPDATE " + table + " SET " + column + "=? WHERE " + where,
                                   ('{"duplicate":1,"duplicate":1}', *arguments))
                self.reject_unchanged(reports.ReportIntegrityError)
                connection.execute("UPDATE " + table + " SET " + column + "=? WHERE " + where, (old, *arguments))

    def test_public_preparation_exact_allowance_boundaries(self):
        """A supported capture prepares at exact caller byte/reference limits and fails one unit below."""
        from research_pipeline.view_capture import _Metadata
        with RecordStore.create(self.parent / "boundary-store") as store:
            populate(store)
            proposal = report_request("boundary").to_dict()
            original_records = report_capture._metadata(self.store, self.store._connection, "first")[2].records
            report_references = 2 + sum(len(record.record_references) + len(record.artifact_references)
                                        for record in original_records)
            # The detached plan also enforces the retained capture allowance on
            # its complete report projection, so provision those same occurrences.
            proposal["limits"]["snapshot"].update(max_roots=2, max_records=2, max_references=report_references,
                                                 max_record_bytes=2000, max_metadata_bytes=20_000)
            store.commit_report(ReportRequest(proposal))
            budgets = []

            def observe_budget(maximum):
                """Retain the real budget instance without changing its accounting or limit decisions."""
                budget = _Metadata(maximum)
                budgets.append(budget)
                return budget

            with patch("research_pipeline.view_capture._Metadata", side_effect=observe_budget):
                original = prepare_report_view(store, "boundary", limits=self.limits)
            self.assertEqual(len(budgets), 1)
            result, _, submission = report_capture._metadata(store, store._connection, "boundary")
            references = len(original.to_dict()["reports"][0]["observation"]["source_bindings"])
            references += sum(len(record.record_references) + len(record.artifact_references) for record in submission.records)
            record_bytes = max(len(_canonical(record.to_dict())) for record in submission.records)
            exact = replace(self.limits, max_metadata_bytes=budgets[0].used,
                            max_record_bytes=record_bytes, max_references=references)
            self.assertGreater(exact.max_metadata_bytes, 20_000)
            self.assertEqual(prepare_report_view(store, "boundary", limits=exact), original)
            before = tree_state(self.parent)
            for name in ("max_metadata_bytes", "max_record_bytes", "max_references"):
                with self.subTest(limit=name), self.assertRaises(SnapshotLimitError):
                    prepare_report_view(store, "boundary", limits=replace(exact, **{name: getattr(exact, name) - 1}))
                self.assertEqual(tree_state(self.parent), before)
            self.assertEqual(store.get_report_operation("boundary"), result)

    def test_receipt_members_keep_original_order(self):
        """Two contiguous members are insufficient when their actual order contradicts the original request."""
        connection = self.store._connection
        connection.execute("UPDATE revisions SET ordinal=ordinal+10 WHERE submission_id='first'")
        connection.execute("UPDATE revisions SET ordinal=11-ordinal WHERE submission_id='first'")
        self.reject_unchanged(reports.ReportIntegrityError)
