"""The MCP tool server, started as a real process and spoken to over stdio, forwards calls to the controller."""
import asyncio
import json
import os
import sys
import unittest

from research_pipeline.channel import serve


class McpServerTest(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.requests = []

        async def handler(request):
            self.requests.append(request)
            return f'handled {request["tool"]}'

        self.name = f'research-pipeline-test-{os.getpid()}'
        self.server = await serve(self.name, handler)

    async def asyncTearDown(self):
        self.server.close()

    async def start(self, role):
        env = os.environ | {'RP_CHANNEL': self.name, 'RP_AGENT': 'helper', 'RP_TOKEN': 'secret', 'RP_ROLE': role}
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'research_pipeline.mcp_server', env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        self.serial = 0
        await self.request('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                          'clientInfo': {'name': 'test', 'version': '0'}})
        await self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    async def send(self, message):
        self.process.stdin.write(json.dumps(message).encode() + b'\n')
        await self.process.stdin.drain()

    async def request(self, method, params=None):
        self.serial += 1
        await self.send({'jsonrpc': '2.0', 'id': self.serial, 'method': method, 'params': params or {}})
        while True:
            reply = json.loads(await asyncio.wait_for(self.process.stdout.readline(), 30))
            if reply.get('id') == self.serial:
                return reply['result']

    async def stop(self):
        self.process.stdin.close()
        await asyncio.wait_for(self.process.wait(), 10)

    async def test_role_tools_and_forwarding(self):
        await self.start('subagent')
        names = {tool['name'] for tool in (await self.request('tools/list'))['tools']}
        self.assertIn('submit_result', names)
        self.assertIn('run_job', names)
        self.assertNotIn('complete', names)
        result = await self.request('tools/call', {'name': 'run_job',
                                                   'arguments': {'command': 'make', 'timeout_seconds': 60}})
        self.assertEqual(result['content'][0]['text'], 'handled run_job')
        self.assertEqual(self.requests[-1], {'agent': 'helper', 'token': 'secret', 'tool': 'run_job',
                                             'args': {'command': 'make', 'timeout_seconds': 60.0, 'cwd': ''}})
        await self.stop()

    async def test_primary_and_reviewer_tools(self):
        await self.start('primary')
        names = {tool['name'] for tool in (await self.request('tools/list'))['tools']}
        self.assertTrue({'complete', 'stop', 'spawn'} <= names)
        self.assertNotIn('verdict', names)
        await self.stop()
        await self.start('reviewer')
        names = {tool['name'] for tool in (await self.request('tools/list'))['tools']}
        self.assertIn('verdict', names)
        await self.stop()


if __name__ == '__main__':
    unittest.main()
