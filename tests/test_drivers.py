"""CLI drivers: the shared transport with a real confined process, and each CLI's command and events."""
import asyncio
import json
import shutil
import sys
import unittest

from research_pipeline.drivers import ClaudeSession, CodexSession, Launch, McpServer, Session
from tests.helpers import remove, temp_project

# A stand-in CLI: answers each message with a text, a context reading and a turn end; 'exit' ends it.
_ECHO_CLI = r'''
import json, sys
for count, line in enumerate(sys.stdin, 1):
    text = json.loads(line)["text"]
    if text == "exit":
        sys.exit(3)
    open("touched.txt", "a").write(text + "\n")
    for event in ({"kind": "text", "text": "echo: " + text}, {"kind": "context", "tokens": 100 * count},
                  {"kind": "end"}):
        print(json.dumps(event), flush=True)
'''


class EchoSession(Session):
    """A minimal driver for the stand-in CLI: everything else is the shared base class."""
    backend = 'echo'

    def command(self):
        return [sys.executable, '-c', _ECHO_CLI]

    async def begin(self):
        await self.deliver(self.launch.message)

    async def deliver(self, text):
        self.busy = True
        await self.write({'text': text})

    def receive(self, message):
        if message['kind'] == 'text':
            self.emit('text', text=message['text'])
        elif message['kind'] == 'context':
            self.emit('context', tokens=message['tokens'], window=1000)
        else:
            self.busy = False
            self.emit('turn_ended', text='')


def launch(root, message='hello'):
    return Launch(agent='a', cwd=root, instructions='Be rigorous.', message=message, model='m', effort='high',
                  mcp=McpServer(['python3', '-m', 'research_pipeline.mcp_server'], {'RP_AGENT': 'a'}),
                  writable=(root,), log=root / 'log.jsonl')


@unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap is not installed')
class TransportTest(unittest.IsolatedAsyncioTestCase):

    async def test_session_lifecycle_inside_confinement(self):
        root = temp_project()
        events = []
        session = EchoSession(launch(root), lambda s, kind, data: events.append((kind, data)))
        try:
            await session.start()
            for _ in range(100):
                if ('turn_ended', {'text': ''}) in events:
                    break
                await asyncio.sleep(0.05)
            self.assertIn(('text', {'text': 'echo: hello'}), events)
            self.assertIn(('context', {'tokens': 100, 'window': 1000}), events)
            await session.send('again')
            await asyncio.sleep(0.5)
            self.assertIn(('text', {'text': 'echo: again'}), events)
            self.assertEqual((root / 'touched.txt').read_text(), 'hello\nagain\n')
            await session.send('exit')
            for _ in range(100):
                if any(kind == 'exited' for kind, _ in events):
                    break
                await asyncio.sleep(0.05)
            exited = [data for kind, data in events if kind == 'exited']
            self.assertTrue(exited and 'status 3' in exited[0]['reason'], events)
            self.assertIn('> {"text": "hello"}', (root / 'log.jsonl').read_text())
        finally:
            await session.close()
            remove(root)


class CodexTest(unittest.TestCase):

    def setUp(self):
        self.root = temp_project()
        self.events = []
        self.session = CodexSession(launch(self.root), lambda s, kind, data: self.events.append((kind, data)))

    def tearDown(self):
        remove(self.root)

    def test_command_attaches_controller_tools_and_disables_native_agents(self):
        command = self.session.command()
        self.assertEqual(command[-1], 'app-server')
        server = next(value for value in command if value.startswith('mcp_servers.research='))
        self.assertIn('default_tools_approval_mode="approve"', server)
        self.assertIn('RP_AGENT="a"', server)
        self.assertIn('features.multi_agent=false', command)
        self.assertIn('model="m"', command)
        self.assertIn('model_reasoning_effort="high"', command)

    def test_events(self):
        session = self.session
        session.turn = 't1'
        for message in (
                {'method': 'turn/started', 'params': {'turn': {'id': 't1'}}},
                {'method': 'item/completed', 'params': {'item': {'type': 'commandExecution', 'command': 'ls',
                                                                 'exitCode': 0}}},
                {'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'text': 'Done.'}}},
                {'method': 'thread/tokenUsage/updated', 'params': {'tokenUsage': {
                    'last': {'totalTokens': 1200}, 'modelContextWindow': 400000}}},
                {'method': 'turn/completed', 'params': {'turn': {'id': 't1', 'status': 'completed'}}}):
            session.receive(message)
        self.assertEqual([kind for kind, _ in self.events], ['tool', 'text', 'context', 'turn_ended'])
        self.assertEqual(self.events[2][1], {'tokens': 1200, 'window': 400000})
        self.assertEqual(self.events[3][1], {'text': 'Done.', 'failed': False})
        self.assertFalse(session.busy)

    def test_failed_turn_and_ended_process(self):
        session = self.session
        session.turn = 't2'
        session.receive({'method': 'turn/completed', 'params': {'turn': {'id': 't2', 'status': 'failed',
                                                                         'error': {'message': 'overloaded'}}}})
        self.assertEqual(self.events[-1], ('turn_ended', {'text': '', 'failed': True}))

        async def scenario():
            future = asyncio.get_running_loop().create_future()
            session._pending[7] = future
            session.ended()  # the app-server died: waiting requests fail at once
            with self.assertRaises(Exception):
                await future
        asyncio.run(scenario())

    def test_replies_resolve_requests(self):
        async def scenario():
            session = self.session
            sent = []

            async def write(message):
                sent.append(message)
                session.receive({'id': message['id'], 'result': {'ok': True}})
            session.write = write
            self.assertEqual(await session.request('thread/start', {}), {'ok': True})
            session.write = lambda message: asyncio.sleep(0, session.receive({'id': message['id'],
                                                                              'error': {'message': 'no'}}))
            with self.assertRaises(Exception):
                await session.request('turn/steer', {})
        asyncio.run(scenario())


class ClaudeTest(unittest.TestCase):

    def setUp(self):
        self.root = temp_project()
        self.events = []
        self.session = ClaudeSession(launch(self.root), lambda s, kind, data: self.events.append((kind, data)))

    def tearDown(self):
        remove(self.root)

    def test_command_and_environment(self):
        command = self.session.command()
        for flag in ('--input-format', 'stream-json', '--append-system-prompt', 'Be rigorous.', 'bypassPermissions',
                     'Task,Agent', '--strict-mcp-config'):
            self.assertIn(flag, command)
        settings = json.loads(command[command.index('--settings') + 1])
        self.assertEqual(settings['sandbox'], {'enabled': False})
        servers = json.loads(command[command.index('--mcp-config') + 1])
        self.assertEqual(servers['mcpServers']['research']['env'], {'RP_AGENT': 'a'})
        environment = self.session.environment()
        self.assertFalse([key for key in environment if key.startswith('CLAUDECODE')])
        self.assertEqual(environment['CLAUDE_CODE_DISABLE_BACKGROUND_TASKS'], '1')

    def test_events(self):
        session = self.session
        session.receive({'type': 'system', 'subtype': 'init', 'model': 'claude-x'})
        session.receive({'type': 'assistant', 'parent_tool_use_id': None, 'message': {
            'usage': {'input_tokens': 10, 'cache_read_input_tokens': 1000, 'output_tokens': 5},
            'content': [{'type': 'text', 'text': 'Working.'}, {'type': 'tool_use', 'name': 'Bash',
                                                                'input': {'command': 'ls'}}]}})
        session.receive({'type': 'assistant', 'parent_tool_use_id': 'nested', 'message': {
            'usage': {'input_tokens': 99999}}})  # a nested call does not fill this session's context
        session.receive({'type': 'result', 'subtype': 'success', 'result': 'Done.',
                         'modelUsage': {'claude-x': {'contextWindow': 200000}}})
        kinds = [kind for kind, _ in self.events]
        self.assertEqual(kinds, ['context', 'text', 'tool', 'context', 'turn_ended'])
        self.assertEqual(self.events[0][1], {'tokens': 1015, 'window': None})
        self.assertEqual(self.events[3][1], {'tokens': 1015, 'window': 200000})
        self.assertEqual(self.events[4][1], {'text': 'Done.', 'failed': False})


if __name__ == '__main__':
    unittest.main()
