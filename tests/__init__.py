"""Test setup for running directly from an uninstalled source checkout."""
import os
from pathlib import Path
import sys


def use_checkout():
    """Use this checkout in tests and in Python CLI subprocesses they launch."""
    source = str(Path(__file__).resolve().parents[1] / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    inherited = os.environ.get("PYTHONPATH", "")
    if source not in inherited.split(os.pathsep):
        os.environ["PYTHONPATH"] = source + (os.pathsep + inherited if inherited else "")


def record_job(config, returncode=0):
    """Controller tests emulate the trusted adapter's admission and result files.

    This is explicitly an execution double, never native enforcement evidence.
    """
    import json
    import uuid
    from research_pipeline import jobs
    context = json.loads(config.job_context.read_text())
    request = {**context, "request_id": uuid.uuid4().hex,
               "argv": ["engineering-execution-double"], "cwd": "/project/" + context["workspace"]}
    root = config.job_context.parent
    jobs.atomic(root / "out/request.json", request)
    config.on_poll()
    ack = jobs.read(root / "in/ack.json")
    if not ack or not ack["accepted"]:
        raise AssertionError(f"Execution double admission failed: {ack}")
    record = {**ack["job"], "state": "completed" if returncode == 0 else "failed",
              "returncode": returncode, "cleanup_ok": True,
              "reason": "Explicit engineering execution double"}
    jobs.atomic(root / "out" / f"{record['job_id']}.json", record)
    config.on_poll()


def job_driver(config, argv, cwd="/project/work"):
    """An inference-free fixture runs through the real adapter inside isolation."""
    from research_pipeline import jobs
    code = f"""
import asyncio, sys
from pathlib import Path
from research_pipeline import jobs
from research_pipeline.job_server import Adapter
async def main():
    adapter = Adapter(jobs.read(Path('/run/research-jobs.json')))
    monitor = asyncio.create_task(adapter.supervise())
    try:
        result = await adapter.run({argv!r}, {cwd!r}, None, 0)
        while result['state'] in jobs.ACTIVE:
            result = await adapter.wait(result['job_id'], 1)
        sys.stdout.write(result.get('stdout', ''))
        sys.stderr.write(result.get('stderr', ''))
        return 124 if result['state'] == 'timed_out' else (result.get('returncode') or (0 if result['state'] == 'completed' else 1))
    finally:
        monitor.cancel()
raise SystemExit(asyncio.run(main()))
"""
    return ["/usr/bin/env", "PYTHONPATH=" + os.pathsep.join(["/opt/research-src", *jobs.adapter_mounts()]),
            sys.executable, "-P", "-s", "-c", code]
