"""Real local protocol/process fixtures; no inference or production-isolation claim."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

from tests import use_checkout
use_checkout()
from research_pipeline import app_server, isolation, jobs


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def fixture(self, behavior='normal'):
        script = r'''
import json, sys
behavior = sys.argv[1]
for line in sys.stdin:
    request = json.loads(line)
    if 'id' not in request: continue
    method = request['method']
    if method == 'initialize':
        result = {'userAgent': 'protocol-double'}
    elif method == 'thread/start':
        result = {'thread': {'id': 'native-thread-double'}}
    elif method == 'turn/start':
        if behavior == 'eof': sys.exit(0)
        if behavior == 'malformed':
            print('not json', flush=True); continue
        if behavior == 'compacted':
            print(json.dumps({'method':'thread/compacted','params':{'threadId':'native-thread-double','turnId':'turn-double'}}),flush=True); continue
        if behavior == 'unexpected':
            print(json.dumps({'id': 999, 'method': 'item/commandExecution/requestApproval'}), flush=True); continue
        if behavior == 'rpc-error':
            print(json.dumps({'id': request['id'], 'error': {'code': -1, 'message': 'unsupported'}}), flush=True); continue
        print(json.dumps({'method': 'thread/tokenUsage/updated', 'params': {'threadId': 'native-thread-double', 'turnId': 'turn-double', 'tokenUsage': {'last': {'totalTokens': 123}, 'total': {'totalTokens': 999}, 'modelContextWindow': 10000}}}), flush=True)
        if behavior == 'waiting':
            print(json.dumps({'id':request['id'],'result':{'turn':{'id':'turn-double'}}}),flush=True)
            continue
        # Exercise completion arriving before the turn/start response.
        status = behavior if behavior in ('failed', 'interrupted') else 'completed'
        error = {'message': 'retained native failure'} if status != 'completed' else None
        print(json.dumps({'method': 'turn/completed', 'params': {'threadId': 'native-thread-double', 'turn': {'id': 'turn-double', 'status': status, 'error': error}}}), flush=True)
        result = {'turn': {'id': 'turn-double'}}
    elif method == 'turn/interrupt':
        print(json.dumps({'method':'turn/completed','params':{'threadId':'native-thread-double','turn':{'id':'turn-double','status':'interrupted'}}}),flush=True)
        result = {}
    else: result = {}
    print(json.dumps({'id': request['id'], 'result': result}), flush=True)
'''
        process = await asyncio.create_subprocess_exec(sys.executable, '-c', script, behavior,
                 stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        class Service:
            async def close(self):
                if process.returncode is None:
                    process.kill()
                await process.wait()
                return {'confirmed': True, 'reason': 'Owned protocol fixture reaped'}
        service = Service()
        service.process = process
        client = app_server.Client(service)
        self.addAsyncCleanup(client.close)
        await client.start()
        await client.new_thread('/project/work')
        return client

    async def test_request_correlation_early_completion_and_distinct_telemetry(self):
        client = await self.fixture()
        turn = await client.turn('Protocol fixture only')
        self.assertEqual(turn['status'], 'completed')
        self.assertEqual(client.telemetry['last']['totalTokens'], 123)
        self.assertEqual(client.telemetry['total']['totalTokens'], 999)
        self.assertEqual(client.telemetry['modelContextWindow'], 10000)
        self.assertIsNone(client.failure)

    async def test_active_turn_interrupt_and_close_resolve_waiters(self):
        client = await self.fixture('waiting')
        pending = asyncio.create_task(client.turn('Wait for a controlled interrupt'))
        await asyncio.wait_for(client.turn_ready.wait(), 2)
        self.assertEqual(client.active_turn_id, 'turn-double')
        await client.interrupt(client.active_turn_id)
        result = await asyncio.wait_for(pending, 2)
        self.assertEqual(result['status'], 'interrupted')
        self.assertIsNone(client.active_turn_id)
        pending = asyncio.create_task(client.turn('Wait for operational closure'))
        await asyncio.sleep(.02)
        await client.close()
        with self.assertRaises(isolation.RuntimeUnavailable):
            await asyncio.wait_for(pending, 2)
        self.assertFalse(client.turns)

    async def test_eof_rpc_errors_malformed_messages_and_requests_fail_observably(self):
        for behavior in ('eof', 'rpc-error', 'malformed', 'unexpected', 'compacted'):
            with self.subTest(behavior=behavior):
                client = await self.fixture(behavior)
                with self.assertRaises(isolation.RuntimeUnavailable):
                    await asyncio.wait_for(client.turn('Fixture'), 2)
                await client.close()

    async def test_failed_and_interrupted_completion_notifications_retain_the_native_outcome(self):
        for status in ('failed', 'interrupted'):
            with self.subTest(status=status):
                client = await self.fixture(status)
                turn = await client.turn('Protocol fixture only')
                self.assertEqual(turn['status'], status)
                self.assertEqual(turn['error'], {'message': 'retained native failure'})
                self.assertIsNone(client.failure)

    async def test_rpc_timeout_does_not_claim_scientific_completion(self):
        process = await asyncio.create_subprocess_exec(sys.executable, '-c', 'import time; time.sleep(30)',
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        class Service:
            async def close(self):
                process.kill()
                await process.wait()
                return {'confirmed': True}
        service = Service()
        service.process = process
        client = app_server.Client(service)
        client.reader = asyncio.create_task(client.read())
        client.stderr = asyncio.create_task(client.read_stderr())
        try:
            with self.assertRaisesRegex(isolation.RuntimeUnavailable, 'Operational RPC timeout'):
                await client.request('initialize', {}, timeout=.05)
        finally:
            await client.close()


class SupervisorProcessTests(unittest.TestCase):
    def test_real_worker_deadline_and_partial_output_survive_transport_absence(self):
        # Fixed engineering process fixture outside Bubblewrap. Production tree
        # isolation and detached descendants are checked only by the native gate.
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            now = time.monotonic()
            record = {'job_id': 'a'*32, 'deadline': now + .5}
            jobs.atomic(root/'request.json', {'record': record, 'argv': [sys.executable, '-u', '-c',
                        "import time; print('partial useful output', flush=True); time.sleep(30)"]})
            jobs.atomic(root/'launch.json', {'job_id': record['job_id']})
            process = subprocess.Popen([sys.executable, '-P', '-s', '-m', 'research_pipeline.jobs', '--supervise', str(root/'request.json')])
            try:
                process.wait(timeout=5)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=3)
            result = jobs.read(root/'result.json')
            self.assertEqual(result['job_id'], record['job_id'])
            self.assertIn('partial useful output', result['stdout'])
            self.assertTrue(result['finished'])
            self.assertNotIn('cleanup_ok', result, 'Only cgroup observation can establish production cleanup')
            self.assertEqual(result['returncode'], -9)
            self.assertEqual(result['termination_cause'], 'expired')
            self.assertGreaterEqual(result['finished_monotonic'], record['deadline'])

    def test_bounded_capture_and_nonzero_command_outcome(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jobs.atomic(root/'request.json', {'record': {'job_id': 'b'*32, 'deadline': time.monotonic()+5},
                       'argv': [sys.executable, '-c', "print('x'*40000); raise SystemExit(7)"]})
            jobs.atomic(root/'launch.json', {'job_id': 'b'*32})
            subprocess.run([sys.executable, '-P', '-s', '-m', 'research_pipeline.jobs', '--supervise', str(root/'request.json')], timeout=8, check=True)
            result = jobs.read(root/'result.json')
            self.assertEqual(result['returncode'], 7)
            self.assertEqual(result['termination_cause'], 'completed')
            self.assertLess(result['finished_monotonic'], jobs.read(root/'request.json')['record']['deadline'])
            self.assertEqual(len(result['stdout']), 8192)
            self.assertTrue(result['stdout_clipped'])
