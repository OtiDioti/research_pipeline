"""The agents' tools: each role's set, offered through the toolkit's MCP tool server (a real process over stdio)."""
import os
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_toolkit.tools import ToolBridge

from research_pipeline.tools import ROLE_TOOLS


class ToolServerTest(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.bridge = ToolBridge()
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.close)
        self.calls = []

    async def listed(self, role, call=None):
        """The tools a ``role`` agent's CLI sees; ``call`` (tool, arguments) is made through the server."""
        server = self.bridge.offer('helper', ROLE_TOOLS[role], lambda tool, args: self.calls.append((tool, args))
                                   or f'handled {tool}', name='research')['research']
        parameters = StdioServerParameters(command=server.command[0], args=server.command[1:],
                                           env={**os.environ, **server.env})
        async with stdio_client(parameters) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            reply = await client.call_tool(*call) if call else None
        self.bridge.withdraw('helper')
        return tools, reply

    async def test_role_tools_and_forwarding(self):
        tools, reply = await self.listed('subagent', ('run_job', {'command': 'make', 'timeout_seconds': 60}))
        self.assertTrue({'submit_result', 'run_job', 'message'} <= set(tools))
        self.assertNotIn('complete', tools)
        self.assertEqual(set(tools['spawn'].inputSchema['required']), {'task', 'backend', 'model', 'effort'})
        self.assertEqual(reply.content[0].text, 'handled run_job')
        self.assertEqual(self.calls, [('run_job', {'command': 'make', 'timeout_seconds': 60})])

    async def test_a_call_missing_a_required_argument_never_reaches_the_controller(self):
        tools, reply = await self.listed('subagent', ('run_job', {'command': 'make'}))
        self.assertTrue(reply.isError)
        self.assertEqual(self.calls, [])

    async def test_primary_and_reviewer_tools(self):
        tools, _ = await self.listed('primary')
        self.assertTrue({'complete', 'stop', 'spawn'} <= set(tools))
        self.assertNotIn('verdict', tools)
        tools, _ = await self.listed('reviewer')
        self.assertIn('verdict', tools)


if __name__ == '__main__':
    unittest.main()
