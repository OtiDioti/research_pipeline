"""Consequential job checks; native scientific fixtures stay inside isolation."""
import asyncio
from contextlib import contextmanager
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from types import SimpleNamespace

from tests import use_checkout
use_checkout()
from research_pipeline import cli, codex, isolation, jobs, references, tools, workspace
from research_pipeline.job_server import Adapter, create_server
from tests.test_isolation import fixture, live_enabled


def setup(root, runtime=1):
    fixture(root)
    (root / "starting_evidence/RESEARCH_QUESTIONS.md").write_text("Engineering fixture only.")
    state = {"run_id": uuid.uuid4().hex, "activation_id": uuid.uuid4().hex,
             "ownership_nonce": uuid.uuid4().hex, "limits": isolation.Config(
                 job_runtime_seconds=runtime).limits(), "active_seconds": 3}
    session = root / ".research_pipeline/session"
    session.mkdir()
    config = isolation.Config(deadline=time.monotonic() + 25, job_runtime_seconds=runtime)
    config.drafts = session / "drafts"
    config.drafts.mkdir()
    config.control, config.response = session / "control", session / "response"
    config.control.mkdir()
    config.response.mkdir()
    references.configure(config, root, session, workspace.read_intake(root))
    tools.configure(config, root, session, state["activation_id"])
    manager = jobs.JobManager(root, state, lambda: None)
    manager.configure(config, session, state)
    return state, config, manager


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state, self.config, self.manager = setup(self.root)
        self.owner = next(iter(self.manager.owners.values()))
        self.request = {**self.owner["identity"], "argv": ["/bin/true"], "cwd": "/project/work"}

    def test_shared_capacity_descendant_cleanup_and_deadline_are_durable(self):
        self.config.deadline = time.monotonic() + .5
        record = self.manager.admit(self.owner, self.request)
        self.assertLessEqual(record["effective_runtime_seconds"], .5)
        self.assertEqual(self.state["active_seconds"], 3)
        child = dict(self.owner, identity={**self.owner["identity"], "task_id": "task-" + uuid.uuid4().hex})
        with self.assertRaisesRegex(jobs.JobError, "capacity exhausted"):
            self.manager.admit(child, {**self.request, **child["identity"]})
        jobs.reconcile(self.state, cleanup_ok=False)
        with self.assertRaisesRegex(jobs.JobError, "capacity exhausted"):
            self.manager.admit(self.owner, self.request)
        jobs.reconcile(self.state, cleanup_ok=True)
        self.assertEqual(record["state"], "interrupted")
        self.manager.admit(self.owner, self.request)

    def test_invalid_runtime_owner_and_cwd_launch_nothing(self):
        for update in ({"runtime_seconds": True}, {"runtime_seconds": 2}, {"runtime_seconds": float("nan")},
                       {"argv": []}, {"ownership_nonce": "other"}, {"cwd": "/tmp"},
                       {"cwd": "/project/starting_evidence"}, {"cwd": "/project/work/../starting_evidence"}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.manager.admit(self.owner, {**self.request, **update})
        self.assertEqual(self.state.get("jobs", {}), {})
        for key, value in (("max_jobs", True), ("max_jobs", 1.5), ("max_jobs", 0),
                           ("job_runtime_seconds", True), ("job_runtime_seconds", "1"),
                           ("job_runtime_seconds", float("inf"))):
            with self.subTest(key=key, value=value), self.assertRaises(jobs.JobError):
                jobs.validate_limits({key: value})

    def test_saving_blocks_science_but_keeps_scoped_drafts(self):
        (self.config.control / "request.json").write_text('{"reason":"pause"}')
        with self.assertRaisesRegex(jobs.JobError, "Saving requested"):
            self.manager.admit(self.owner, self.request)
        context = json.loads(self.config.job_context.read_text())
        adapter = Adapter(context)
        with patch.object(workspace, "safe_path", side_effect=lambda root, rel: self.config.drafts / rel):
            adapter.draft("handoffs/primary.md", "# Useful partial work\nData saved; calculation interrupted.")
        self.assertTrue((self.config.drafts / "handoffs/primary.md").exists())
        for path in ("starting_evidence/questions.md", "work/tasks/private.md", "../escape.md"):
            with self.assertRaises(ValueError):
                adapter.draft(path, "invalid")

    def test_adapter_protocol_exposes_only_fixed_operations(self):
        server = create_server(Adapter(json.loads(self.config.job_context.read_text())))
        listing = asyncio.run(server.list_tools())
        self.assertEqual({t.name for t in listing},
                         {"job_run", "job_wait", "job_status", "job_cancel", "write_draft", "control"})
        command = codex.build_command(self.config)
        self.assertIn("features.shell_tool=false", command)
        self.assertIn('mcp_servers.research_jobs.required=true', command)
        self.assertIn("workspace-write", command)
        self.assertIn("--ignore-user-config", command)

    def test_native_catalog_check_rejects_bypasses_and_missing_adapter(self):
        catalog = [{"name": "mcp__research_jobs__" + name} for name in
                   ("job_run", "job_wait", "job_status", "job_cancel", "write_draft", "control")]
        self.assertEqual(len(codex.validate_tool_catalog(catalog)), 6)
        for unsafe in ("exec_command", "functions.write_stdin", "shell_command", "mcp__other__run"):
            with self.assertRaisesRegex(isolation.RuntimeUnavailable, "Unsupported native"):
                codex.validate_tool_catalog([*catalog, {"name": unsafe}])
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "adapter unavailable"):
            codex.validate_tool_catalog(catalog[:-1])
        with self.assertRaisesRegex(isolation.RuntimeUnavailable, "execution tool"):
            codex.validate_tool_catalog([*catalog, {"name": "exec", "description": "Runs host commands"}])
        text = codex.CATALOG_MARKER + json.dumps(catalog)
        events = [{"type": "item.completed", "item": {"type": "agent_message", "text": text}},
                  {"type": "item.completed", "item": {"type": "code_execution", "arguments": text}}]
        self.assertEqual(codex.native_catalog_observations(events), [])
        events.append({"type": "item.completed", "item": {"type": "code_execution",
                       "source": codex.CATALOG_SOURCE,
                       "result": {"content": [{"text": text}]}}})
        self.assertEqual(codex.native_catalog_observations(events), [catalog])

    def test_lost_adapter_reservation_is_retained_until_service_cleanup(self):
        record = self.manager.admit(self.owner, self.request)
        self.manager.owner_stopped(self.state["activation_id"], False)
        self.assertEqual(record["state"], "cleanup_unconfirmed")
        self.assertFalse(record["cleanup_ok"])
        jobs.reconcile(self.state, cleanup_ok=True)
        self.assertTrue(record["cleanup_ok"])
        self.assertEqual(jobs.observed(self.state)["successful_commands"], 0)
        self.assertEqual(self.state["active_seconds"], 3)

    def test_budget_report_keeps_unknown_usage_and_lost_intervals_explicit(self):
        self.state.update(accounting_pending=True, activation_started_monotonic=90,
                          boot_id="known", usage_complete=False, usage_totals=None)
        with patch.object(cli, "boot_identity", return_value="known"), \
             patch.object(cli.time, "monotonic", return_value=100):
            live = cli.budget_report(self.state, live=True)
            self.assertEqual(live["active_seconds_observed"], 13)
            self.assertEqual(live["remaining_seconds_observed"], 587)
            lost = cli.budget_report(self.state, live=False)
            self.assertIsNone(lost["remaining_seconds_observed"])
            self.assertFalse(lost["active_time_complete"])
            self.assertIsNone(live["model_usage_observed"])
        self.assertEqual(self.state["active_seconds"], 3)

    def test_capacity_waits_for_namespace_reaping_after_launcher_exit(self):
        record = self.manager.admit(self.owner, self.request)
        runner = jobs.RunningJob(record, {}, self.owner["root"] / "out")
        runner.info.write_text(json.dumps({"child-pid": 123}))
        streams = []
        for _ in range(2):
            read_fd, write_fd = os.pipe()
            os.close(write_fd)
            streams.append(os.fdopen(read_fd, "rb"))
        runner.process = SimpleNamespace(wait=lambda timeout: 0, poll=lambda: 0,
            returncode=0, stdout=streams[0], stderr=streams[1])
        observed = []
        def exists():
            observed.append(True)
            with self.assertRaisesRegex(jobs.JobError, "capacity exhausted"):
                self.manager.admit(self.owner, self.request)
            return len(observed) < 3
        native_path = Path
        def path(value):
            return SimpleNamespace(exists=exists) if value == "/proc/123" else native_path(value)
        with patch.object(jobs, "Path", side_effect=path), patch.object(jobs.signal, "setitimer"):
            runner.finish("completed", "Command completed.")
        self.assertGreaterEqual(len(observed), 3)
        self.assertEqual(record["state"], "reserved")
        self.manager.poll()
        self.assertTrue(record["cleanup_ok"])
        self.assertEqual(record["state"], "completed")
        self.manager.admit(self.owner, self.request)

    def test_status_remains_readable_after_large_history_and_fresh_context(self):
        template = self.manager.admit(self.owner, self.request)
        first_id = template["job_id"]
        template.update(state="completed", cleanup_ok=True, returncode=0,
                        stdout="o" * 8192, stderr="e" * 8192)
        for _ in range(47):
            job_id = uuid.uuid4().hex
            self.state["jobs"][job_id] = {**template, "job_id": job_id}
        old_activation = self.state["activation_id"]
        self.assertGreater(len(json.dumps({"jobs": list(self.state["jobs"].values())})), 256 * 1024)
        self.manager.poll()
        self.manager.owner_stopped(old_activation, True)

        session = self.root / ".research_pipeline/next-session"
        session.mkdir()
        config = replace(self.config, job_context=None)
        next_owner = {**self.state, "activation_id": uuid.uuid4().hex}
        self.manager.configure(config, session, next_owner)
        owner = self.manager.owners[next_owner["activation_id"]]
        running = self.manager.admit(owner, {**self.request, **owner["identity"]})
        self.manager.poll()
        adapter = Adapter(json.loads(config.job_context.read_text()),
                          incoming=owner["root"] / "in", outgoing=owner["root"] / "out")
        snapshot = adapter.status()
        self.assertLess((adapter.incoming / "status.json").stat().st_size, 256 * 1024)
        self.assertEqual(snapshot["occupied"], 1)
        self.assertEqual(snapshot["max_jobs"], 1)
        self.assertEqual(snapshot["jobs_total"], 49)
        self.assertEqual(snapshot["jobs_omitted"], 49 - jobs.STATUS_JOB_LIMIT)
        self.assertEqual(snapshot["jobs"][0]["job_id"], running["job_id"])
        self.assertEqual(len(snapshot["jobs"]), jobs.STATUS_JOB_LIMIT)
        self.assertNotIn(first_id, [r["job_id"] for r in snapshot["jobs"]])
        self.assertTrue(all("stdout" not in r and "stderr" not in r and "argv" not in r
                            for r in snapshot["jobs"]))
        detail = adapter.status(first_id)
        self.assertEqual(detail["activation_id"], old_activation)
        self.assertEqual(detail["stdout"], "o" * 8192)
        self.assertEqual(detail["stderr"], "e" * 8192)
        with self.assertRaisesRegex(jobs.JobError, "Unknown job"):
            adapter.cancel(first_id)
        with self.assertRaisesRegex(jobs.JobError, "Unknown job"):
            adapter.status("../status")


# Inference-free engineering fixtures exercise the real nested launcher, not a
# command supplied to the researcher as its scientific solution.
NATIVE = r'''
import asyncio, json, os
from pathlib import Path
from research_pipeline import codex, isolation, jobs
from research_pipeline.job_server import Adapter
async def main():
    # Native stdio transport, without inference, before direct supervisor fixtures.
    import sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    settings = codex.build_command(isolation.Config())
    adapter_args = json.loads(next(s.split('=', 1)[1] for s in settings
        if s.startswith('mcp_servers.research_jobs.args=')))
    parameters = StdioServerParameters(command=sys.executable,
        args=adapter_args, env={'PYTHONPATH':os.environ['PYTHONPATH']})
    async with stdio_client(parameters) as (incoming, outgoing):
        async with ClientSession(incoming, outgoing) as session:
            await session.initialize()
            listing = await session.list_tools()
            assert {t.name for t in listing.tools} == {
                'job_run','job_wait','job_status','job_cancel','write_draft','control'}
            check = await session.call_tool('control', {'action':'check'})
            assert not check.isError, check
            call = await session.call_tool('job_run', {
                'argv':['/usr/bin/python3','-c','print(285)'], 'cwd':'/project/work', 'yield_seconds':1})
            assert not call.isError, call
            result = call.structuredContent or json.loads(call.content[0].text)
            while result['state'] in jobs.ACTIVE:
                call = await session.call_tool('job_wait', {'job_id':result['job_id'],'bounded_wait_seconds':1})
                result = call.structuredContent or json.loads(call.content[0].text)
            assert result['state'] == 'completed' and result['stdout'].strip() == '285', result
            status_call = await session.call_tool('job_status', {})
            status = status_call.structuredContent or json.loads(status_call.content[0].text)
            assert 'jobs' in status and 'occupied' in status and 'max_jobs' in status, status
            print('MCP result received', file=sys.stderr, flush=True)
    print('MCP transport closed', file=sys.stderr, flush=True)
    adapter = Adapter(jobs.read(Path('/run/research-jobs.json')))
    monitor = asyncio.create_task(adapter.supervise())
    async def run(code, runtime=None):
        result = await adapter.run(['/usr/bin/python3', '-c', code], '/project/work', runtime, 0)
        while result['state'] in jobs.ACTIVE and result['state'] != 'cleanup_unconfirmed':
            result = await adapter.wait(result['job_id'], 1)
        assert result['cleanup_ok'], result
        return result
    try:
        ok = await run("from pathlib import Path; Path('/project/work/value').write_text(str(sum(i*i for i in range(10)))); Path('/project/work/cgroup').write_text(Path('/proc/self/cgroup').read_text()); print('285')")
        print('normal completed', file=sys.stderr, flush=True)
        assert ok['state'] == 'completed' and ok['returncode'] == 0, ok
        assert Path('/project/work/value').read_text() == '285'
        assert Path('/project/work/cgroup').read_text() == Path('/proc/self/cgroup').read_text()
        pending = await adapter.run(['/usr/bin/python3', '-c',
            "from pathlib import Path; import time; Path('/project/work/partial').write_text('retained'); time.sleep(20)"],
            '/project/work', None, 0)
        try:
            await adapter.run(['/bin/true'], '/project/work', None, 0)
        except ValueError as exc:
            assert 'capacity exhausted' in str(exc), exc
        else:
            raise AssertionError('concurrent job admitted')
        while pending['state'] in jobs.ACTIVE:
            pending = await adapter.wait(pending['job_id'], 1)
        assert pending['state'] == 'timed_out' and pending['cleanup_ok'], pending
        timeout = dict(pending)
        print('timeout completed', file=sys.stderr, flush=True)
        assert Path('/project/work/partial').read_text() == 'retained'
        # Closed and inherited descriptors: foreground exit alone is insufficient.
        for close in (False, True):
            child = ("import os,time; os.setsid(); " +
                     ("os.close(1); os.close(2); " if close else "") +
                     "time.sleep(1); open('/project/work/escaped', 'w').write('bad')")
            result = await run("import subprocess; subprocess.Popen(['/usr/bin/python3','-c'," + repr(child) + "])")
            assert result['state'] == 'completed', result
            await asyncio.sleep(1.1)
            assert not Path('/project/work/escaped').exists(), result
        print('descendants completed', file=sys.stderr, flush=True)
        failed = await run("raise SystemExit(7)")
        assert failed['returncode'] == 7 and failed['state'] == 'failed', failed
        absent = await adapter.run(['/missing-executable'], '/project/work', None, 0)
        while absent['state'] in jobs.ACTIVE:
            absent = await adapter.wait(absent['job_id'], 1)
        assert absent['state'] == 'failed' and absent['cleanup_ok'], absent
        assert 'missing-executable' in absent['stderr'], absent
        print('failures completed', file=sys.stderr, flush=True)
        await run("from pathlib import Path; assert not Path('/run/research-jobs-out').exists(); assert not Path('/run/research-jobs.json').exists(); assert not Path('/home/researcher/.codex/auth.json').exists()")
        pending = await adapter.run(['/usr/bin/python3', '-c',
                                    "from pathlib import Path; import time; Path('/project/work/pause-ready').touch(); time.sleep(20)"],
                                    '/project/work', None, 0)
        while not Path('/project/work/pause-ready').exists():
            await asyncio.sleep(.02)
        Path('/project/work/request-pause').touch()
        while pending['state'] in jobs.ACTIVE:
            pending = await adapter.wait(pending['job_id'], 1)
        assert pending['state'] == 'interrupted' and pending['cleanup_ok'], pending
        print('pause completed', file=sys.stderr, flush=True)
        try:
            await adapter.run(['/bin/true'], '/project/work', None, 0)
        except ValueError as exc:
            assert 'Saving requested' in str(exc), exc
        else:
            raise AssertionError('scientific work admitted while saving')
        adapter.draft('handoffs/primary.md', '# Partial work retained\nJob stopped for pause; inspect data before restarting.')
        assert not Path('/project/work/shadow-imported').exists(), 'untrusted package ran outside the scientific job'
        print(json.dumps({'normal':ok, 'timeout':timeout, 'pause':pending, 'failed':failed, 'missing':absent}), flush=True)
    finally:
        monitor.cancel()
asyncio.run(main())
'''


class NativeJobTests(unittest.TestCase):
    def require_service(self):
        if not os.environ.get("DBUS_SESSION_BUS_ADDRESS") or not os.environ.get("XDG_RUNTIME_DIR"):
            if live_enabled():
                self.fail("Enabled job boundary check requires the production user bus")
            self.skipTest("Production user bus unavailable; controller-host verification required")

    @contextmanager
    def directory(self):
        if os.environ.get("RESEARCH_PIPELINE_M4_LIVE") == "1":
            output = os.environ.get("RESEARCH_PIPELINE_M4_OUTPUT_DIR")
            self.assertTrue(output, "Enabled M4 job checks require RESEARCH_PIPELINE_M4_OUTPUT_DIR")
            Path(output).mkdir(parents=True, exist_ok=True)
            root = Path(tempfile.mkdtemp(prefix="job-boundary-", dir=output))
            root.chmod(0o700)
            yield root  # enabled controller-host receipts and partial artifacts are retained
        else:
            with tempfile.TemporaryDirectory() as tmp:
                yield Path(tmp)

    def receipt(self, root, config, state, argv, result, output):
        receipt = {"config": asdict(config), "state": state, "argv": argv,
                   "result": asdict(result) if isinstance(result, isolation.ExecutionResult) else result,
                   "bounded_output": output, "kind": "Inference-free production-boundary engineering fixture"}
        (root / ".research_pipeline/receipt.json").write_text(json.dumps(receipt, indent=2, default=str))
        if os.environ.get("RESEARCH_PIPELINE_M4_LIVE") == "1":
            print("\nJob boundary receipt: " + str(root / ".research_pipeline/receipt.json") + "\n"
                  + json.dumps(receipt, indent=2, default=str), flush=True)

    def test_nested_namespace_timeout_and_descendant_teardown(self):
        with self.directory() as root:
            state, config, manager = setup(root, runtime=1.5)
            shadow = root / "work/research_pipeline"
            shadow.mkdir()
            for name in ("__init__.py", "jobs.py", "job_server.py"):
                (shadow / name).write_text(
                    "from pathlib import Path\n"
                    "Path('/project/work/shadow-imported').write_text('untrusted import')\n"
                    "raise RuntimeError('research workspace shadowed the trusted runtime')\n")
            # The test owner polls while the fixture executes in the same mounts
            # as a production agent. This path needs no user bus or inference.
            command = isolation.bubblewrap_command(root, [sys.executable, "-P", "-s", "-c", NATIVE],
                drafts=config.drafts, control=config.control, response=config.response,
                reference_mounts=config.reference_mounts, reference_catalog=config.reference_catalog,
                tool_context=config.tool_context, job_context=config.job_context)
            env = ["--setenv", "PYTHONPATH", os.pathsep.join(["/opt/research-src", *jobs.adapter_mounts()])]
            offset = command.index("--chdir")
            command[offset:offset] = env
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 24
                while process.poll() is None and time.monotonic() < deadline:
                    if (root / "work/request-pause").exists():
                        jobs.atomic(config.control / "request.json", {"reason": "pause"})
                    manager.poll()
                    time.sleep(.02)
                if process.poll() is None:
                    process.kill()
                stdout, stderr = process.communicate(timeout=3)
                if process.returncode and "Operation not permitted" in stderr and not live_enabled():
                    self.skipTest("Nested namespaces unavailable: " + stderr)
                self.assertEqual(process.returncode, 0, stdout + stderr + "\n" + json.dumps(state.get("jobs"), indent=2))
                self.assertFalse((root / "work/shadow-imported").exists())
                manager.owner_stopped(state["activation_id"], True)
                self.receipt(root, config, state, command, {"returncode": process.returncode}, stdout + stderr)
                self.assertTrue(all(r["cleanup_ok"] for r in state["jobs"].values()))
                self.assertEqual(state["active_seconds"], 3)
                self.assertTrue(any(r["state"] == "timed_out" for r in state["jobs"].values()))
                self.assertTrue((config.drafts / "handoffs/primary.md").is_file())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_production_service_job_tree_remains_in_original_grant(self):
        self.require_service()
        with self.directory() as root:
            state, config, manager = setup(root, runtime=1.5)
            config.memory_mib, config.max_tasks = 512, 128
            state["limits"] = config.limits()
            enforced = {}
            def poll():
                if (root / "work/request-pause").exists():
                    jobs.atomic(config.control / "request.json", {"reason": "pause"})
                manager.poll()
                if state.get("jobs") and not enforced:
                    props = isolation.service_properties(config.unit)
                    group = Path("/sys/fs/cgroup") / props["ControlGroup"].lstrip("/")
                    enforced.update({n: (group / n).read_text().strip()
                                     for n in ("memory.max", "memory.swap.max", "pids.max")})
                    self.assertEqual(enforced, {"memory.max": str(512 * 1024 * 1024),
                                                "memory.swap.max": "0", "pids.max": "128"})
            config.on_poll = poll
            # The Python runtime is mounted with the adapter. Use a tiny shell to
            # set its import path, inside the same original service grant.
            argv = ["/usr/bin/env", "PYTHONPATH=" + os.pathsep.join(
                ["/opt/research-src", *jobs.adapter_mounts()]), sys.executable, "-P", "-s", "-c", NATIVE]
            output = bytearray()
            result = isolation.run_isolated(config, root, argv,
                on_event=lambda channel, data: output.extend(data[:max(0, 32768-len(output))]))
            manager.owner_stopped(state["activation_id"], result.cleanup_ok)
            state["observed_cgroup_limits"] = enforced
            self.receipt(root, config, state, argv, result, output.decode(errors="replace"))
            self.assertEqual(result.returncode, 0, output.decode(errors="replace"))
            self.assertTrue(result.cleanup_ok)
            self.assertTrue(all(r["cleanup_ok"] for r in state["jobs"].values()))
            self.assertTrue(enforced)

    def test_service_interruption_recovers_job_reservation_after_full_cleanup(self):
        self.require_service()
        from tests import job_driver
        with self.directory() as root:
            state, config, manager = setup(root, runtime=10)
            original = dict(state["limits"])
            code = ("from pathlib import Path; import subprocess,time\n"
                    "subprocess.Popen(['/usr/bin/python3','-c',"
                    "\"import os,time; os.setsid(); time.sleep(2); open('/project/work/escaped','w').write('bad')\"])\n"
                    "Path('/project/work/ready').touch(); time.sleep(20)")
            argv = job_driver(config, ["/usr/bin/python3", "-c", code])
            def poll():
                manager.poll()
                return "pause" if (root / "work/ready").exists() else None
            output = bytearray()
            result = isolation.run_isolated(config, root, argv, poll=poll,
                on_event=lambda channel, data: output.extend(data[:max(0, 8192-len(output))]))
            manager.owner_stopped(state["activation_id"], result.cleanup_ok)
            self.receipt(root, config, state, argv, result, output.decode(errors="replace"))
            self.assertEqual(result.requested_stop, "pause")
            self.assertTrue(result.cleanup_ok)
            self.assertTrue(state["jobs"])
            self.assertTrue(all(r["cleanup_ok"] and r["state"] not in jobs.ACTIVE for r in state["jobs"].values()))
            self.assertEqual(state["limits"], original)
            time.sleep(2.1)
            self.assertFalse((root / "work/escaped").exists())
